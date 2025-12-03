package xyz.xingfeng.tingfeng.llm.config;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class LlmConfigInitializer {
    @Bean
    ApplicationRunner llmConfigGenerator() {
        return args -> {
            String defaultPath = "config/llm.yaml";
            String pathStr = System.getenv().getOrDefault("LLM_CONFIG_PATH", defaultPath);
            Path path = Paths.get(pathStr);
            if (Files.notExists(path)) {
                Path dir = path.getParent();
                if (dir != null && Files.notExists(dir)) {
                    Files.createDirectories(dir);
                }
                String content = defaultContent();
                Files.writeString(path, content, StandardCharsets.UTF_8);
            }
        };
    }

    private String defaultContent() throws IOException {
        return """
llm:
  platforms:
    openai:
      base_urls:
        default: https://api.openai.com/v1
      api_keys:
        default: ${OPENAI_API_KEY}
      urls:
        chat: /chat/completions
        images: /images
        embeddings: /embeddings
      models:
        - alias: openai-gpt-4o-mini
          name: gpt-4o-mini
          base_url_ref: default
          url_ref: chat
          api_key_ref: default
          capabilities: [text, vision]
        - alias: openai-gpt-4o
          name: gpt-4o
          base_url_ref: default
          url_ref: chat
          api_key_ref: default
          capabilities: [text, vision]
        - alias: openai-emb-3-large
          name: text-embedding-3-large
          base_url_ref: default
          url_ref: embeddings
          api_key_ref: default
          capabilities: [embedding]

    azure_openai:
      base_urls:
        default: https://{resource}.openai.azure.com
      api_keys:
        default: ${AZURE_OPENAI_API_KEY}
      urls:
        chat: /openai/deployments/{deployment}/chat/completions?api-version=2024-08-01-preview
      models:
        - alias: azure-gpt-4o
          name: gpt-4o
          base_url_ref: default
          url_ref: chat
          api_key_ref: default
          deployment: gpt-4o
          capabilities: [text, vision]

    qwen:
      base_urls:
        default: https://dashscope.aliyuncs.com
      api_keys:
        default: ${DASHSCOPE_API_KEY}
      urls:
        chat: /api/v1/services/aigc/text-generation/generation
      models:
        - alias: qwen-vl
          name: qwen-vl
          base_url_ref: default
          url_ref: chat
          api_key_ref: default
          capabilities: [vision]

    deepseek:
      base_urls:
        default: https://api.deepseek.com
      api_keys:
        default: ${DEEPSEEK_API_KEY}
      urls:
        chat: /chat/completions
      models:
        - alias: deepseek-vl
          name: deepseek-vl
          base_url_ref: default
          url_ref: chat
          api_key_ref: default
          capabilities: [vision]

    moonshot:
      base_urls:
        default: https://api.moonshot.cn
      api_keys:
        default: ${MOONSHOT_API_KEY}
      urls:
        chat: /v1/chat/completions
      models:
        - alias: moonshot-v1-vision
          name: moonshot-v1-vision
          base_url_ref: default
          url_ref: chat
          api_key_ref: default
          capabilities: [vision]

    siliconflow:
      base_urls:
        default: https://api.siliconflow.cn
      api_keys:
        default: ${SILICONFLOW_API_KEY}
      urls:
        chat: /v1/chat/completions
      models:
        - alias: siliconflow-llava-vl
          name: llava-vl
          base_url_ref: default
          url_ref: chat
          api_key_ref: default
          capabilities: [vision]

    glm:
      base_urls:
        default: https://open.bigmodel.cn/api
      api_keys:
        default: ${ZHIPU_API_KEY}
      urls:
        chat: /paas/v4/chat/completions
      models:
        - alias: glm-4v
          name: glm-4v
          base_url_ref: default
          url_ref: chat
          api_key_ref: default
          capabilities: [vision]

    ollama:
      base_urls:
        default: http://localhost:11434
      api_keys: {}
      urls:
        chat: /api/chat
      models:
        - alias: ollama-llama3.2-vision
          name: llama3.2-vision
          base_url_ref: default
          url_ref: chat
          capabilities: [vision]

  routing:
    chat: openai-gpt-4o-mini
    vision: openai-gpt-4o
    image_caption: qwen-vl
    ocr: qwen-vl
    reply_summarization: openai-gpt-4o-mini
    forward_unwrap: openai-gpt-4o-mini
    embedding: openai-emb-3-large
""";
    }
}
