package com.tide.video.service;

import com.tide.video.client.RecClient;
import com.tide.video.entity.Behavior;
import com.tide.video.entity.Video;
import com.tide.video.repository.BehaviorRepository;
import com.tide.video.repository.VideoRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
public class FeedService {

    private final VideoRepository videoRepository;
    private final BehaviorRepository behaviorRepository;
    private final RecClient recClient;

    @Value("${rec.media-url:http://localhost:8000}")
    private String mediaUrl;

    public FeedService(VideoRepository videoRepository, BehaviorRepository behaviorRepository, RecClient recClient) {
        this.videoRepository = videoRepository;
        this.behaviorRepository = behaviorRepository;
        this.recClient = recClient;
    }

    public Map<String, Object> feed(Long userId, int count) {
        List<Video> videos = videoRepository.findAll();
        if (videos.isEmpty()) {
            return Map.of("items", List.of(), "personalized", userId != null);
        }
        List<Behavior> behaviors = userId == null ? List.of() : behaviorRepository.findByUserId(userId);

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("user_id", userId);
        payload.put("count", count);
        payload.put("videos", videos.stream().map(this::videoDto).collect(Collectors.toList()));
        payload.put("behaviors", behaviors.stream().map(this::behaviorDto).collect(Collectors.toList()));

        List<Map<String, Object>> items = recClient.recommend(payload);

        // 推荐服务不可用 -> 热门兜底
        if (items.isEmpty()) {
            items = hotFallback(videos, count);
        }

        Map<Long, Video> byId = videos.stream().collect(Collectors.toMap(Video::getId, Function.identity()));
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> it : items) {
            Object vidObj = it.get("video_id");
            Long vid = vidObj instanceof Number ? ((Number) vidObj).longValue() : null;
            Video v = vid == null ? null : byId.get(vid);
            if (v == null) {
                continue;
            }
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id", v.getId());
            m.put("title", v.getTitle());
            m.put("category", v.getCategory());
            m.put("tags", splitTags(v.getTags()));
            m.put("url", mediaUrl + "/media/" + v.getFilename());
            m.put("views", v.getViews());
            m.put("likes", v.getLikes());
            m.put("reason", it.getOrDefault("reason", "热门视频"));
            result.add(m);
        }
        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("items", result);
        resp.put("personalized", userId != null);
        return resp;
    }

    private Map<String, Object> videoDto(Video v) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", v.getId());
        m.put("title", v.getTitle());
        m.put("category", v.getCategory());
        m.put("tags", splitTags(v.getTags()));
        m.put("views", v.getViews());
        m.put("likes", v.getLikes());
        m.put("created_at", v.getCreatedAt() / 1000.0);
        return m;
    }

    private Map<String, Object> behaviorDto(Behavior b) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("user_id", b.getUserId());
        m.put("video_id", b.getVideoId());
        m.put("event", b.getEvent());
        m.put("watch_ratio", b.getWatchRatio());
        m.put("created_at", b.getCreatedAt() / 1000.0);
        return m;
    }

    private List<Map<String, Object>> hotFallback(List<Video> videos, int count) {
        return videos.stream()
                .sorted(Comparator.comparingInt((Video v) -> v.getViews() + v.getLikes() * 3).reversed())
                .limit(count)
                .map(v -> {
                    Map<String, Object> m = new LinkedHashMap<>();
                    m.put("video_id", v.getId());
                    m.put("reason", "热门视频");
                    return m;
                })
                .collect(Collectors.toList());
    }

    private List<String> splitTags(String tags) {
        if (tags == null || tags.isBlank()) {
            return List.of();
        }
        List<String> out = new ArrayList<>();
        for (String t : tags.split(",")) {
            if (!t.isBlank()) {
                out.add(t.trim());
            }
        }
        return out;
    }
}