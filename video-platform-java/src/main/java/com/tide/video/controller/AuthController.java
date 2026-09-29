package com.tide.video.controller;

import com.tide.video.entity.User;
import com.tide.video.service.AuthService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    @PostMapping("/register")
    public Map<String, Object> register(@RequestBody Map<String, String> body) {
        try {
            return authService.register(body.get("username"), body.get("password"));
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage());
        }
    }

    @PostMapping("/login")
    public Map<String, Object> login(@RequestBody Map<String, String> body) {
        try {
            return authService.login(body.get("username"), body.get("password"));
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, e.getMessage());
        }
    }

    @GetMapping("/me")
    public Map<String, Object> me(@RequestHeader(value = "Authorization", required = false) String auth) {
        Long uid = authService.userIdFromToken(bearer(auth));
        Optional<User> user = authService.findById(uid);
        Map<String, Object> m = new LinkedHashMap<>();
        if (user.isPresent()) {
            Map<String, Object> u = new LinkedHashMap<>();
            u.put("id", user.get().getId());
            u.put("username", user.get().getUsername());
            m.put("user", u);
        } else {
            m.put("user", null);
        }
        return m;
    }

    static String bearer(String auth) {
        return (auth != null && auth.startsWith("Bearer ")) ? auth.substring(7) : null;
    }
}