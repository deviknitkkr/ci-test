package com.example.citest.controller;

import io.micrometer.core.annotation.Timed;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.Random;

@RestController
public class PingController {
    private static String podName = System.getenv("POD_NAME");
    private final Random random = new Random();

    @GetMapping("/ping")
    @Timed(value = "ping_request_duration", description = "Time taken to process ping requests")
    public Map<String, Object> ping() throws Exception {
        // Simulate occasional errors (5% of the time)
        if (random.nextDouble() < 0.05) {
            throw new RuntimeException("Simulated error");
        }

        // Simulate some processing time
        try {
            Thread.sleep(random.nextInt(50) + 10);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        return Map.of(
            "status", "ok",
            "message", "pong",
            "timestamp", LocalDateTime.now(),
            "podName", podName
        );
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "UP");
    }
}
