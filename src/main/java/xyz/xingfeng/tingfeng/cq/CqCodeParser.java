package xyz.xingfeng.tingfeng.cq;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class CqCodeParser {
    public List<MessageSegment> parse(String input) {
        List<MessageSegment> segments = new ArrayList<>();
        if (input == null || input.isEmpty()) {
            return segments;
        }
        int i = 0;
        int len = input.length();
        while (i < len) {
            int start = input.indexOf("[CQ:", i);
            if (start < 0) {
                segments.add(MessageSegment.text(input.substring(i)));
                break;
            }
            if (start > i) {
                segments.add(MessageSegment.text(input.substring(i, start)));
            }
            int end = findClosingBracket(input, start + 1);
            if (end < 0) {
                segments.add(MessageSegment.text(input.substring(start)));
                break;
            }
            String content = input.substring(start + 4, end);
            CqSegment cq = parseCq(content);
            if (cq == null) {
                segments.add(MessageSegment.text(input.substring(start, end + 1)));
            } else {
                segments.add(MessageSegment.cq(cq));
            }
            i = end + 1;
        }
        return segments;
    }

    private int findClosingBracket(String s, int from) {
        for (int j = from; j < s.length(); j++) {
            char c = s.charAt(j);
            if (c == ']') {
                return j;
            }
        }
        return -1;
    }

    private CqSegment parseCq(String content) {
        String type;
        Map<String, String> data = new LinkedHashMap<>();
        int comma = content.indexOf(',');
        if (comma < 0) {
            type = content;
            return new CqSegment(type, data);
        } else {
            type = content.substring(0, comma);
            String paramStr = content.substring(comma + 1);
            String[] parts = splitParams(paramStr);
            boolean invalid = false;
            for (String p : parts) {
                String part = p.trim();
                if (part.isEmpty()) continue;
                int eq = part.indexOf('=');
                if (eq > 0) {
                    String k = part.substring(0, eq).trim();
                    String v = decode(part.substring(eq + 1));
                    data.put(k, v);
                } else {
                    invalid = true;
                    break;
                }
            }
            if (invalid) {
                return null;
            }
            return new CqSegment(type, data);
        }
    }

    private String[] splitParams(String s) {
        List<String> list = new ArrayList<>();
        StringBuilder cur = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == ',') {
                list.add(cur.toString());
                cur.setLength(0);
            } else {
                cur.append(c);
            }
        }
        list.add(cur.toString());
        return list.toArray(new String[0]);
    }

    public String decode(String s) {
        if (s == null || s.isEmpty()) {
            return s;
        }
        String r = s;
        r = r.replace("&amp;", "&");
        r = r.replace("&#91;", "[");
        r = r.replace("&#93;", "]");
        r = r.replace("&#44;", ",");
        return r;
    }
}
