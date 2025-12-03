package xyz.xingfeng.tingfeng.cq;

public class MessageSegment {
    private boolean cq;
    private String text;
    private CqSegment cqSegment;

    public MessageSegment() {}

    @Override
    public String toString() {
        return text;
    }

    public static MessageSegment text(String text) {
        MessageSegment s = new MessageSegment();
        s.cq = false;
        s.text = text;
        return s;
    }

    public static MessageSegment cq(CqSegment cq) {
        MessageSegment s = new MessageSegment();
        s.cq = true;
        s.cqSegment = cq;
        return s;
    }

    public boolean isCq() {
        return cq;
    }

    public void setCq(boolean cq) {
        this.cq = cq;
    }

    public String getText() {
        return text;
    }

    public void setText(String text) {
        this.text = text;
    }

    public CqSegment getCqSegment() {
        return cqSegment;
    }

    public void setCqSegment(CqSegment cqSegment) {
        this.cqSegment = cqSegment;
    }
}
