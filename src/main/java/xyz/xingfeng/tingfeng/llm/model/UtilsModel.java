package xyz.xingfeng.tingfeng.llm.model;

import java.util.Base64;

import xyz.xingfeng.tingfeng.llm.config.LlmAliasExample;
import xyz.xingfeng.tingfeng.llm.config.LlmAliasExample.ModelConfig;

/**
 * 工具模型
 */
public class UtilsModel {
    /**
     * 普通图片识别模型工具
     * 让模型理解图片中的内容，并返回内容描述
     * @param image 图片内容
     * @return 图片内容描述
     * @throws Exception 
     */
    public String imageRecognition(byte[] image) throws Exception {
        ModelConfig modelConfig = LlmAliasExample.resolve(LlmAliasExample.resolveRouting("image_caption"));
        String imageBase64 = Base64.getEncoder().encodeToString(image);
        
        return "图片内容描述";
    }

    
}
