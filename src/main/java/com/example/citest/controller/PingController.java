package com.example.citest.controller;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.Random;

@RestController
public class PingController {
    private static String podName = System.getenv("POD_NAME");

    private final Counter pingRequestCounter;
    private final Counter pingErrorCounter;
    private final Timer pingRequestTimer;
    private final Random random = new Random();

    @Autowired
    public PingController(MeterRegistry meterRegistry) {
        this.pingRequestCounter = Counter.builder("ping_requests_total")
                .description("Total number of ping requests")
                .tag("endpoint", "ping")
                .register(meterRegistry);

        this.pingErrorCounter = Counter.builder("ping_errors_total")
                .description("Total number of ping errors")
                .tag("endpoint", "ping")
                .register(meterRegistry);

        this.pingRequestTimer = Timer.builder("ping_request_duration_seconds")
                .description("Time taken to process ping requests")
                .tag("endpoint", "ping")
                .register(meterRegistry);
    }

    @GetMapping("/ping")
    public Map<String, Object> ping() throws Exception{
        return pingRequestTimer.recordCallable(() -> {
            pingRequestCounter.increment();

            // Simulate occasional errors (5% of the time)
            if (random.nextDouble() < 0.05) {
                pingErrorCounter.increment();
                throw new RuntimeException("Simulated error");
            }

            // Simulate some processing time
            try {
                Thread.sleep(random.nextInt(100) + 10);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }

            return Map.of(
                "status", "ok",
                "message", "pong",
                "timestamp", LocalDateTime.now(),
                "podName", podName
            );
        });
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "UP");
    }
}
