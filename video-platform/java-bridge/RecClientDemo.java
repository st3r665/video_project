import java.io.*;
import java.net.*;

public class RecClientDemo {
    static String base = "http://localhost:8000";

    public static void main(String[] args) throws Exception {
        String login = postJson("/api/login", "{\"username\":\"demo\",\"password\":\"demo123\"}");
        String token = extract(login, "token");
        System.out.println("[1] login ok, token=" + token.substring(0, 12) + "...");

        String feed = get("/api/feed?count=8", token);
        int n = countOccurrences(feed, "\"title\"");
        System.out.println("[2] personalized feed returned " + n + " videos:");
        printField(feed, "title");

        String hot = get("/api/feed?count=3", null);
        System.out.println("[3] anonymous hot feed also ok (" + countOccurrences(hot, "\"title\"") + " videos)");
        System.out.println("[4] DONE: Java 8 called the Python service over HTTP successfully");
    }

    static String postJson(String path, String body) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(base + path).openConnection();
        c.setRequestMethod("POST");
        c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json");
        try (OutputStream os = c.getOutputStream()) { os.write(body.getBytes("UTF-8")); }
        return readAll(c);
    }

    static String get(String path, String token) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(base + path).openConnection();
        c.setRequestMethod("GET");
        if (token != null) c.setRequestProperty("Authorization", "Bearer " + token);
        return readAll(c);
    }

    static String readAll(HttpURLConnection c) throws Exception {
        InputStream in = c.getResponseCode() < 400 ? c.getInputStream() : c.getErrorStream();
        BufferedReader r = new BufferedReader(new InputStreamReader(in, "UTF-8"));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = r.readLine()) != null) sb.append(line);
        return sb.toString();
    }

    static String extract(String json, String key) {
        int i = json.indexOf("\"" + key + "\"");
        int s = json.indexOf("\"", i + key.length() + 3);
        int e = json.indexOf("\"", s + 1);
        return json.substring(s + 1, e);
    }

    static int countOccurrences(String s, String sub) {
        int c = 0, i = 0;
        while ((i = s.indexOf(sub, i)) != -1) { c++; i += sub.length(); }
        return c;
    }

    static void printField(String json, String key) {
        String marker = "\"" + key + "\"";
        int i = 0;
        while ((i = json.indexOf(marker, i)) != -1) {
            int colon = json.indexOf(":", i + marker.length());
            int s = json.indexOf("\"", colon + 1);
            int e = json.indexOf("\"", s + 1);
            if (s < 0 || e < 0) break;
            System.out.println("    - " + json.substring(s + 1, e));
            i = e + 1;
        }
    }
}