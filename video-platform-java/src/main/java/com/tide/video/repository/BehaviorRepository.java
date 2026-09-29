package com.tide.video.repository;

import com.tide.video.entity.Behavior;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface BehaviorRepository extends JpaRepository<Behavior, Long> {
    List<Behavior> findByUserId(Long userId);
    List<Behavior> findAllByOrderByCreatedAtAsc();
}