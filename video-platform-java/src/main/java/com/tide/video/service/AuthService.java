package com.tide.video.service;

import com.tide.video.entity.User;
import com.tide.video.repository.UserRepository;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final Map<String, Long> tokens = new ConcurrentHashMap<>();
    private static final SecureRandom RANDOM = new SecureRandom();

    public AuthService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    public Map<String, Object> register(String username, String password) {
        if (username == null || !username.matches("[\\w\\u4e00-\\u9fa5]{2,20}")) {
            throw new IllegalArgumentException("用户名需为 2~20 位字母/数字/下划线/中文");
        }
        if (password == null || password.length() < 6) {
            throw new IllegalArgumentException("密码至少 6 位");
        }
        if (userRepository.findByUsername(username).isPresent()) {
            throw new IllegalArgumentException("用户名已被占用");
        }
        byte[] salt = new byte[16];
        RANDOM.nextBytes(salt);
        User user = new User(username, hash(password, salt), Base64.getEncoder().encodeToString(salt), System.currentTimeMillis());
        userRepository.save(user);
        return tokenResponse(user);
    }

    public Map<String, Object> login(String username, String password) {
        Optional<User> opt = userRepository.findByUsername(username == null ? "" : username);
        if (opt.isEmpty()) {
            throw new IllegalArgumentException("用户名或密码错误");
        }
        User user = opt.get();
        byte[] salt = Base64.getDecoder().decode(user.getSalt());
        if (!user.getPasswordHash().equals(hash(password, salt))) {
            throw new IllegalArgumentException("用户名或密码错误");
        }
        return tokenResponse(user);
    }

    public Long userIdFromToken(String token) {
        return token == null ? null : tokens.get(token);
    }

    public Optional<User> findByUsername(String username) {
        return userRepository.findByUsername(username);
    }

    public Optional<User> findById(Long id) {
        return id == null ? Optional.empty() : userRepository.findById(id);
    }

    private Map<String, Object> tokenResponse(User user) {
        String token = UUID.randomUUID().toString().replace("-", "");
        tokens.put(token, user.getId());
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("token", token);
        Map<String, Object> u = new LinkedHashMap<>();
        u.put("id", user.getId());
        u.put("username", user.getUsername());
        m.put("user", u);
        return m;
    }

    private String hash(String password, byte[] salt) {
        try {
            PBEKeySpec spec = new PBEKeySpec(password.toCharArray(), salt, 100000, 256);
            byte[] hash = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
                    .generateSecret(spec).getEncoded();
            return Base64.getEncoder().encodeToString(hash);
        } catch (Exception e) {
            throw new RuntimeException("密码哈希失败", e);
        }
    }
}