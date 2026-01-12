package xyz.xingfeng.tingfeng.llm.model;

import org.json.JSONArray;
import org.json.JSONObject;

public class OpenAiRequestBuilder {
    private final JSONObject root = new JSONObject();
    private final JSONArray messages = new JSONArray();

    /**
     * 设置使用的模型名称
     * @param model 模型名称，例如 gpt-4o-mini
     * @return 构建器本身
     */
    public OpenAiRequestBuilder setModel(String model) {
        root.put("model", model);
        return this;
    }

    /**
     * 设置是否使用流式传输
     * @param stream true 开启流式，false 关闭
     * @return 构建器本身
     */
    public OpenAiRequestBuilder setStream(boolean stream) {
        root.put("stream", stream);
        return this;
    }

    /**
     * 设置最大生成的 token 数
     * @param maxTokens 最大 token 数
     * @return 构建器本身
     */
    public OpenAiRequestBuilder setMaxTokens(int maxTokens) {
        root.put("max_tokens", maxTokens);
        return this;
    }

    /**
     * 设置温度（采样随机性）
     * @param temperature 0.0-2.0 区间常用
     * @return 构建器本身
     */
    public OpenAiRequestBuilder setTemperature(double temperature) {
        root.put("temperature", temperature);
        return this;
    }

    /**
     * 设置 Top-p 采样
     * @param topP 0.0-1.0
     * @return 构建器本身
     */
    public OpenAiRequestBuilder setTopP(double topP) {
        root.put("top_p", topP);
        return this;
    }

    /**
     * 设置出现惩罚
     * @param presencePenalty 惩罚系数
     * @return 构建器本身
     */
    public OpenAiRequestBuilder setPresencePenalty(double presencePenalty) {
        root.put("presence_penalty", presencePenalty);
        return this;
    }

    /**
     * 设置频率惩罚
     * @param frequencyPenalty 惩罚系数
     * @return 构建器本身
     */
    public OpenAiRequestBuilder setFrequencyPenalty(double frequencyPenalty) {
        root.put("frequency_penalty", frequencyPenalty);
        return this;
    }

    /**
     * 设置随机种子
     * @param seed 随机种子
     * @return 构建器本身
     */
    public OpenAiRequestBuilder setSeed(long seed) {
        root.put("seed", seed);
        return this;
    }

    /**
     * 添加 system 角色的纯文本信息
     * @param text 文本内容
     * @return 构建器本身
     */
    public OpenAiRequestBuilder addSystemText(String text) {
        JSONObject m = new JSONObject();
        m.put("role", "system");
        m.put("content", text);
        messages.put(m);
        return this;
    }

    /**
     * 添加 assistant 角色的纯文本信息
     * @param text 文本内容
     * @return 构建器本身
     */
    public OpenAiRequestBuilder addAssistantText(String text) {
        JSONObject m = new JSONObject();
        m.put("role", "assistant");
        m.put("content", text);
        messages.put(m);
        return this;
    }

    /**
     * 在 user 角色消息中追加纯文本片段
     * 若当前最后一条为 user 且内容为数组，则复用，否则新建一条 user 消息
     * @param text 文本内容
     * @return 构建器本身
     */
    public OpenAiRequestBuilder addUserText(String text) {
        JSONObject m = ensureUserMessageWithArrayContent();
        JSONArray content = m.getJSONArray("content");
        JSONObject part = new JSONObject();
        part.put("type", "text");
        part.put("text", text);
        content.put(part);
        return this;
    }

    /**
     * 在 user 角色消息中追加图片（URL）片段，detail 默认 auto
     * @param url 图片 URL
     * @return 构建器本身
     */
    public OpenAiRequestBuilder addUserImageUrl(String url) {
        return addUserImageUrl(url, "auto");
    }

    /**
     * 在 user 角色消息中追加图片（URL）片段
     * @param url 图片 URL 或 data:URI
     * @param detail 细节级别：auto、high、low
     * @return 构建器本身
     */
    public OpenAiRequestBuilder addUserImageUrl(String url, String detail) {
        JSONObject m = ensureUserMessageWithArrayContent();
        JSONArray content = m.getJSONArray("content");
        JSONObject part = new JSONObject();
        part.put("type", "image_url");
        JSONObject img = new JSONObject();
        img.put("url", url);
        img.put("detail", detail);
        part.put("image_url", img);
        content.put(part);
        return this;
    }

    /**
     * 在 user 角色消息中追加图片（Base64）片段
     * @param base64 图片的 base64 数据（不含头）
     * @param mime MIME 类型，如 image/png
     * @return 构建器本身
     */
    public OpenAiRequestBuilder addUserImageBase64(String base64, String mime) {
        return addUserImageUrl("data:" + mime + ";base64," + base64, "auto");
    }

    /**
     * 生成最终请求体 JSON
     * @return 请求体对象
     */
    public JSONObject build() {
        root.put("messages", messages);
        return root;
    }

    /**
     * 确保存在一条 user 消息且其 content 为数组
     * 若可复用则返回最后一条，否则创建新的 user 消息
     * @return 可写入内容的 user 消息对象
     */
    private JSONObject ensureUserMessageWithArrayContent() {
        if (messages.length() > 0) {
            JSONObject last = messages.getJSONObject(messages.length() - 1);
            if ("user".equals(last.optString("role"))) {
                Object c = last.opt("content");
                if (c instanceof JSONArray) {
                    return last;
                }
            }
        }
        JSONObject m = new JSONObject();
        m.put("role", "user");
        m.put("content", new JSONArray());
        messages.put(m);
        return m;
    }
}
