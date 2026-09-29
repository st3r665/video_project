package com.tide.video.controller;

import com.tide.video.entity.Behavior;
import com.tide.video.entity.Video;
import com.tide.video.repository.BehaviorRepository;
import com.tide.video.repository.VideoRepository;
import com.tide.video.service.AuthService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class BehaviorController {

    private final AuthService authService;
    private final BehaviorRepository behaviorRepository;
    private final VideoRepository videoRepository;

    public BehaviorController(AuthService authService, BehaviorRepository behaviorRepository, VideoRepository videoRepository) {
        this.authService = authService;
        this.behaviorRepository = behaviorRepository;
        this.videoRepository = videoRepository;
    }

    @PostMapping("/behaviors")
    public Map<String, Object> record(
            @RequestBody Map<String, Object> body,
            @RequestHeader(value = "Authorization", required = false) String auth) {
        Long uid = authService.userIdFromToken(AuthController.bearer(auth));
        if (uid == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "请先登录");
        }
        long videoId = ((Number) body.get("video_id")).longValue();
        String event = String.valueOf(body.get("event"));
        if (!List.of("view", "progress", "finish", "like", "unlike").contains(event)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "event 不合法");
        }
        double ratio = body.get("watch_ratio") instanceof Number
                ? ((Number) body.get("watch_ratio")).doubleValue() : 0.0;
        Video v = videoRepository.findById(videoId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "视频不存在"));

        behaviorRepository.save(new Behavior(uid, videoId, event, ratio, System.currentTimeMillis()));
        if ("view".equals(event)) {
            v.setViews(v.getViews() + 1);
        } else if ("like".equals(event)) {
            v.setLikes(v.getLikes() + 1);
        } else if ("unlike".equals(event)) {
            v.setLikes(Math.max(0, v.getLikes() - 1));
        }
        videoRepository.save(v);
        return Map.of("ok", true);
    }
}