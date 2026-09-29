package com.tide.video.entity;

import jakarta.persistence.*;

@Entity
@Table(name = "behaviors")
public class Behavior {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long userId;

    @Column(nullable = false)
    private Long videoId;

    @Column(nullable = false)
    private String event;

    private double watchRatio;

    @Column(nullable = false)
    private Long createdAt;

    public Behavior() {}

    public Behavior(Long userId, Long videoId, String event, double watchRatio, Long createdAt) {
        this.userId = userId;
        this.videoId = videoId;
        this.event = event;
        this.watchRatio = watchRatio;
        this.createdAt = createdAt;
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }
    public Long getVideoId() { return videoId; }
    public void setVideoId(Long videoId) { this.videoId = videoId; }
    public String getEvent() { return event; }
    public void setEvent(String event) { this.event = event; }
    public double getWatchRatio() { return watchRatio; }
    public void setWatchRatio(double watchRatio) { this.watchRatio = watchRatio; }
    public Long getCreatedAt() { return createdAt; }
    public void setCreatedAt(Long createdAt) { this.createdAt = createdAt; }
}