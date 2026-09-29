package com.tide.video.controller;

import com.tide.video.service.AuthService;
import com.tide.video.service.FeedService;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class FeedController {

    private final AuthService authService;
    private final FeedService feedService;

    public FeedController(AuthService authService, FeedService feedService) {
        this.authService = authService;
        this.feedService = feedService;
    }

    @GetMapping("/feed")
    public Map<String, Object> feed(
            @RequestParam(defaultValue = "12") int count,
            @RequestHeader(value = "Authorization", required = false) String auth) {
        Long uid = authService.userIdFromToken(AuthController.bearer(auth));
        return feedService.feed(uid, Math.max(1, Math.min(count, 30)));
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("status", "up");
        m.put("service", "video-backend");
        return m;
    }
}