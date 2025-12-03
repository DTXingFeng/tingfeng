package xyz.xingfeng.tingfeng.cq;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class CqExtractor {
    public static List<String> texts(List<MessageSegment> segments) {
        List<String> list = new ArrayList<>();
        for (MessageSegment s : segments) {
            if (!s.isCq() && s.getText() != null && !s.getText().isEmpty()) {
                list.add(s.getText());
            }
        }
        return list;
    }

    public static List<Image> images(List<MessageSegment> segments) {
        List<Image> list = new ArrayList<>();
        for (MessageSegment s : segments) {
            if (s.isCq() && "image".equals(s.getCqSegment().getType())) {
                Map<String, String> d = s.getCqSegment().getData();
                String url = d.get("url");
                String file = d.get("file");
                String sub = d.get("sub_type");
                boolean sticker = "1".equals(sub);
                list.add(new Image(url, file, sub, sticker));
            }
        }
        return list;
    }

    public static String replyId(List<MessageSegment> segments) {
        for (MessageSegment s : segments) {
            if (s.isCq() && "reply".equals(s.getCqSegment().getType())) {
                return s.getCqSegment().getData().get("id");
            }
        }
        return null;
    }

    public static String forwardId(List<MessageSegment> segments) {
        for (MessageSegment s : segments) {
            if (s.isCq() && "forward".equals(s.getCqSegment().getType())) {
                return s.getCqSegment().getData().get("id");
            }
        }
        return null;
    }

    public static List<String> ats(List<MessageSegment> segments) {
        List<String> list = new ArrayList<>();
        for (MessageSegment s : segments) {
            if (s.isCq() && "at".equals(s.getCqSegment().getType())) {
                String qq = s.getCqSegment().getData().get("qq");
                if (qq != null) {
                    list.add(qq);
                }
            }
        }
        return list;
    }

    public record Image(String url, String file, String subType, boolean sticker) {}
}
