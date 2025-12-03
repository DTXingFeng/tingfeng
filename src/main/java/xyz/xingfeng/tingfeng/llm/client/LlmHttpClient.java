package xyz.xingfeng.tingfeng.llm.client;

import okhttp3.OkHttpClient;

public class LlmHttpClient {
    OkHttpClient client = new OkHttpClient.Builder()
        .build();
    public LlmHttpClient() {
        
    }
}
