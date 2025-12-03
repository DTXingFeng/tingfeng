package xyz.xingfeng.tingfeng.cq;

import java.util.Map;

public class CqSegment {
    private String type;
    private Map<String, String> data;

    @Override
    public String toString() {
        return String.format("[CQ:%s,%s]", type, data);
    }

    public CqSegment() {}

    public CqSegment(String type, Map<String, String> data) {
        this.type = type;
        this.data = data;
    }

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public Map<String, String> getData() {
        return data;
    }

    public void setData(Map<String, String> data) {
        this.data = data;
    }
}
