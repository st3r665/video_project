package com.tide.video.entity;

import jakarta.persistence.*;

@Entity
@Table(name = "videos")
public class Video {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String title;

    @Column(nullable = false)
    private String category;

    private String tags;

    @Column(nullable = false)
    private String filename;

    private Long uploaderId;

    @Column(nullable = false)
    private Long createdAt;

    private int views;
    private int likes;

    public Video() {}

    public Video(String title, String category, String tags, String filename, Long createdAt) {
        this.title = title;
        this.category = category;
        this.tags = tags;
        this.filename = filename;
        this.createdAt = createdAt;
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public String getCategory() { return category; }
    public void setCategory(String category) { this.category = category; }
    public String getTags() { return tags; }
    public void setTags(String tags) { this.tags = tags; }
    public String getFilename() { return filename; }
    public void setFilename(String filename) { this.filename = filename; }
    public Long getUploaderId() { return uploaderId; }
    public void setUploaderId(Long uploaderId) { this.uploaderId = uploaderId; }
    public Long getCreatedAt() { return createdAt; }
    public void setCreatedAt(Long createdAt) { this.createdAt = createdAt; }
    public int getViews() { return views; }
    public void setViews(int views) { this.views = views; }
    public int getLikes() { return likes; }
    public void setLikes(int likes) { this.likes = likes; }
}