package xyz.xingfeng.tingfeng.cq;

import java.util.List;

public class CqRenderer {
    public String render(List<MessageSegment> segments) {
        StringBuilder sb = new StringBuilder();
        for (MessageSegment s : segments) {
            if (!s.isCq()) {
                sb.append(s.getText());
            } else {
                CqSegment cq = s.getCqSegment();
                String t = cq.getType();
                String v;
                if ("at".equals(t)) {
                    String qq = cq.getData().get("qq");
                    if ("all".equals(qq)) {
                        sb.append("@全体成员");
                    } else {
                        sb.append("@").append(qq);
                    }
                } else if ("image".equals(t)) {
                    v = cq.getData().get("url");
                    if (v == null || v.isEmpty()) v = cq.getData().get("file");
                    if (v == null || v.isEmpty()) sb.append("[图片]"); else sb.append("[图片:").append(v).append("]");
                } else if ("cardimage".equals(t)) {
                    v = cq.getData().get("url");
                    if (v == null || v.isEmpty()) v = cq.getData().get("file");
                    if (v == null || v.isEmpty()) sb.append("[卡片图片]"); else sb.append("[卡片图片:").append(v).append("]");
                } else if ("record".equals(t)) {
                    v = cq.getData().get("url");
                    if (v == null || v.isEmpty()) v = cq.getData().get("file");
                    if (v == null || v.isEmpty()) sb.append("[语音]"); else sb.append("[语音:").append(v).append("]");
                } else if ("video".equals(t)) {
                    v = cq.getData().get("file");
                    if (v == null || v.isEmpty()) v = cq.getData().get("url");
                    if (v == null || v.isEmpty()) sb.append("[视频]"); else sb.append("[视频:").append(v).append("]");
                } else if ("face".equals(t)) {
                    v = cq.getData().get("id");
                    sb.append("[表情:").append(v == null ? "" : v).append("]");
                } else if ("location".equals(t)) {
                    String lat = cq.getData().get("lat");
                    String lon = cq.getData().get("lon");
                    sb.append("[位置:").append(lat == null ? "" : lat).append(",").append(lon == null ? "" : lon).append("]");
                } else if ("share".equals(t)) {
                    v = cq.getData().get("title");
                    sb.append("[分享:").append(v == null ? "" : v).append("]");
                } else if ("music".equals(t)) {
                    String type = cq.getData().get("type");
                    String id = cq.getData().get("id");
                    sb.append("[音乐:").append(type == null ? "" : type).append(" ").append(id == null ? "" : id).append("]");
                } else if ("contact".equals(t)) {
                    String type = cq.getData().get("type");
                    String id = cq.getData().get("id");
                    sb.append("[推荐:").append(type == null ? "" : type).append(" ").append(id == null ? "" : id).append("]");
                } else if ("rps".equals(t)) {
                    sb.append("[猜拳]");
                } else if ("dice".equals(t)) {
                    sb.append("[掷骰子]");
                } else if ("shake".equals(t)) {
                    sb.append("[戳一戳]");
                } else if ("anonymous".equals(t)) {
                    sb.append("[匿名]");
                } else {
                    sb.append("[").append(t).append("]");
                }
            }
        }
        return sb.toString();
    }
}
