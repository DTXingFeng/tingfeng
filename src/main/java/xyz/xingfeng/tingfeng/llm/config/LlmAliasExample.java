package xyz.xingfeng.tingfeng.llm.config;

import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

import org.yaml.snakeyaml.Yaml;

public class LlmAliasExample {

    public static class ModelConfig {
        public final String alias;
        public final String modelName;
        public final String baseUrl;
        public final String path;
        public final String apiKey;
        public final Map<String, String> extras;
        public ModelConfig(String alias, String modelName, String baseUrl, String path, String apiKey, Map<String, String> extras) {
            this.alias = alias;
            this.modelName = modelName;
            this.baseUrl = baseUrl;
            this.path = path;
            this.apiKey = apiKey;
            this.extras = extras;
        }
        public String endpoint() {
            return baseUrl + path;
        }
        @Override
        public String toString() {
            return String.format("ModelConfig{alias=%s, modelName=%s, baseUrl=%s, path=%s, apiKey=%s, extras=%s}",
                    alias, modelName, baseUrl, path, apiKey, extras);
        }
    }

    @SuppressWarnings("unchecked")
    public static ModelConfig resolve(String alias) throws Exception {
        String cfgPath = System.getenv().getOrDefault("LLM_CONFIG_PATH", "config/llm.yaml");
        try (InputStream in = Files.newInputStream(Paths.get(cfgPath))) {
            Map<String, Object> root = new Yaml().load(in);
            Map<String, Object> llm = (Map<String, Object>) root.get("llm");
            Map<String, Object> platforms = (Map<String, Object>) llm.get("platforms");
            for (Map.Entry<String, Object> pe : platforms.entrySet()) {
                Map<String, Object> p = (Map<String, Object>) pe.getValue();
                Map<String, String> baseUrls = (Map<String, String>) p.getOrDefault("base_urls", Collections.emptyMap());
                Map<String, String> urls = (Map<String, String>) p.getOrDefault("urls", Collections.emptyMap());
                Map<String, String> apiKeys = (Map<String, String>) p.getOrDefault("api_keys", Collections.emptyMap());
                List<Map<String, Object>> models = (List<Map<String, Object>>) p.getOrDefault("models", Collections.emptyList());
                for (Map<String, Object> m : models) {
                    String a = (String) m.get("alias");
                    if (alias.equals(a)) {
                        String name = (String) m.get("name");
                        String baseRef = (String) m.get("base_url_ref");
                        String urlRef = (String) m.get("url_ref");
                        String keyRef = (String) m.get("api_key_ref");
                        String base = baseUrls.getOrDefault(baseRef, "");
                        String path = urls.getOrDefault(urlRef, "");
                        String key = apiKeys.getOrDefault(keyRef, "");
                        Map<String, String> extras = new HashMap<>();
                        for (Map.Entry<String, Object> e : m.entrySet()) {
                            Object v = e.getValue();
                            if (v instanceof String) extras.put(e.getKey(), (String) v);
                        }
                        if (base.contains("{resource}")) {
                            String resource = System.getenv().getOrDefault("AZURE_OPENAI_RESOURCE", extras.getOrDefault("resource", ""));
                            base = base.replace("{resource}", resource);
                        }
                        if (path.contains("{deployment}")) {
                            String deployment = extras.getOrDefault("deployment", "");
                            path = path.replace("{deployment}", deployment);
                        }
                        return new ModelConfig(alias, name, base, path, key, extras);
                    }
                }
            }
        }
        throw new IllegalArgumentException("alias not found: " + alias);
    }

    /**
     * 查看x任务需要用的模型别名
     */
    public static String resolveRouting(String task) throws Exception {
        String cfgPath = System.getenv().getOrDefault("LLM_CONFIG_PATH", "config/llm.yaml");
        try (InputStream in = Files.newInputStream(Paths.get(cfgPath))) {
            Map<String, Object> root = new Yaml().load(in);
            Map<String, Object> llm = (Map<String, Object>) root.get("llm");
            Map<String, String> routing = (Map<String, String>) llm.getOrDefault("routing", Collections.emptyMap());
            return routing.getOrDefault(task, "");
        }
    }
}