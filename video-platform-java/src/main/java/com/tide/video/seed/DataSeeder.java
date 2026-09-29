package com.tide.video.seed;

import com.tide.video.entity.Behavior;
import com.tide.video.entity.Video;
import com.tide.video.repository.BehaviorRepository;
import com.tide.video.repository.UserRepository;
import com.tide.video.repository.VideoRepository;
import com.tide.video.service.AuthService;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * 首次启动时写入演示数据：5 个账号 + 24 条视频（6 分类 x 4）+ 若干行为。
 * 视频文件名与 Python 侧 media/ 目录下的种子视频一一对应。
 */
@Component
public class DataSeeder implements CommandLineRunner {

    private static final String[] CATS = {"篮球", "美食", "音乐", "旅行", "科技", "搞笑"};
    private static final String[][] TAGS = {
            {"扣篮,NBA,集锦", "投篮,教学", "街球,实战", "联赛,高光"},
            {"探店,小吃", "家常菜,教程", "烘焙,甜点", "火锅,夜宵"},
            {"吉他,弹唱", "钢琴,纯音乐", "民谣,现场", "电音,混音"},
            {"徒步,风景", "城市,游记", "海边,日落", "雪山,攻略"},
            {"手机,评测", "编程,开发", "AI,前沿", "数码,开箱"},
            {"萌宠,日常", "段子,脱口秀", "整活,创意", "沙雕,合集"},
    };

    private final UserRepository userRepository;
    private final VideoRepository videoRepository;
    private final BehaviorRepository behaviorRepository;
    private final AuthService authService;

    public DataSeeder(UserRepository userRepository, VideoRepository videoRepository,
                      BehaviorRepository behaviorRepository, AuthService authService) {
        this.userRepository = userRepository;
        this.videoRepository = videoRepository;
        this.behaviorRepository = behaviorRepository;
        this.authService = authService;
    }

    @Override
    public void run(String... args) {
        if (userRepository.count() > 0) {
            return;
        }
        Map<String, Long> uid = new HashMap<>();
        uid.put("demo", seedUser("demo", "demo123"));
        uid.put("alice", seedUser("alice", "123456"));
        uid.put("bob", seedUser("bob", "123456"));
        uid.put("carol", seedUser("carol", "123456"));
        uid.put("dave", seedUser("dave", "123456"));

        Map<String, List<Long>> byCat = new HashMap<>();
        long now = System.currentTimeMillis();
        Random rnd = new Random(2026);
        for (int c = 0; c < CATS.length; c++) {
            List<Long> ids = new ArrayList<>();
            for (int i = 1; i <= 4; i++) {
                String filename = "seed_" + CATS[c] + "_" + i + ".mp4";
                long createdAt = now - (long) (rnd.nextDouble() * 8 * 86400 * 1000);
                Video v = new Video(CATS[c] + " · 精选片段 " + i, CATS[c], TAGS[c][i - 1], filename, createdAt);
                v = videoRepository.save(v);
                ids.add(v.getId());
            }
            byCat.put(CATS[c], ids);
        }

        seedPrefs(uid.get("alice"), new String[]{"美食", "音乐"}, byCat, rnd);
        seedPrefs(uid.get("bob"), new String[]{"篮球", "科技"}, byCat, rnd);
        seedPrefs(uid.get("carol"), new String[]{"旅行", "搞笑"}, byCat, rnd);
        seedPrefs(uid.get("dave"), new String[]{"篮球", "美食"}, byCat, rnd);
        seedDemo(uid.get("demo"), byCat.get("篮球"), rnd);

        recalcCounters();
    }

    private long seedUser(String username, String password) {
        Map<String, Object> r = authService.register(username, password);
        @SuppressWarnings("unchecked")
        Map<String, Object> u = (Map<String, Object>) r.get("user");
        return ((Number) u.get("id")).longValue();
    }

    private void seedPrefs(long uid, String[] prefs, Map<String, List<Long>> byCat, Random rnd) {
        long now = System.currentTimeMillis();
        for (String cat : prefs) {
            for (long vid : byCat.get(cat)) {
                double ratio = 0.7 + rnd.nextDouble() * 0.3;
                long ts = now - (long) (rnd.nextDouble() * 6 * 86400 * 1000 + 3600 * 1000);
                behaviorRepository.save(new Behavior(uid, vid, "view", 0, ts));
                behaviorRepository.save(new Behavior(uid, vid, "progress", ratio, ts + 30000));
                if (ratio >= 0.9) {
                    behaviorRepository.save(new Behavior(uid, vid, "finish", 1, ts + 60000));
                }
                if (rnd.nextDouble() < 0.65) {
                    behaviorRepository.save(new Behavior(uid, vid, "like", 0, ts + 90000));
                }
            }
        }
    }

    private void seedDemo(long uid, List<Long> basketball, Random rnd) {
        long now = System.currentTimeMillis();
        for (int i = 0; i < 3; i++) {
            long vid = basketball.get(i);
            long ts = now - (long) ((i + 1) * 3600 * 1000 + rnd.nextDouble() * 1800 * 1000);
            behaviorRepository.save(new Behavior(uid, vid, "view", 0, ts));
            behaviorRepository.save(new Behavior(uid, vid, "progress", 0.8 + rnd.nextDouble() * 0.2, ts + 30000));
        }
        behaviorRepository.save(new Behavior(uid, basketball.get(0), "like", 0, now - 1500000));
    }

    private void recalcCounters() {
        Map<Long, int[]> stat = new HashMap<>();
        for (Behavior b : behaviorRepository.findAllByOrderByCreatedAtAsc()) {
            int[] s = stat.computeIfAbsent(b.getVideoId(), k -> new int[2]);
            if ("view".equals(b.getEvent())) {
                s[0]++;
            }
            if ("like".equals(b.getEvent())) {
                s[1]++;
            }
        }
        for (Video v : videoRepository.findAll()) {
            int[] s = stat.get(v.getId());
            if (s != null) {
                v.setViews(s[0]);
                v.setLikes(s[1]);
                videoRepository.save(v);
            }
        }
    }
}