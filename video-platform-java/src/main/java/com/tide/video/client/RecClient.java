package com.tide.video.client;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * 推荐服务客户端：通过 HTTP 调用 Python 侧的无状态推荐接口 /api/recommend。
 * Python 不可用时返回空列表（FeedService 会降级为热门兜底）。
 */
@Service
public class RecClient {

    private final RestTemplate restTemplate;

    @Value("${rec.service-url:http://localhost:8000}")
    private String serviceUrl;

    public RecClient(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> recommend(Map<String, Object> payload) {
        try {
            Map<String, Object> resp = restTemplate.postForObject(
                    serviceUrl + "/api/recommend", payload, Map.class);
            if (resp != null && resp.get("items") instanceof List) {
                return (List<Map<String, Object>>) resp.get("items");
            }
        } catch (Exception ignored) {
            // 降级：推荐服务不可用时由 FeedService 走热门兜底
        }
        return Collections.emptyList();
    }
}