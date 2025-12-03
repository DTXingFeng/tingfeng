package xyz.xingfeng.tingfeng.Plugin;

import org.springframework.stereotype.Component;

import com.mikuac.shiro.annotation.AnyMessageHandler;
import com.mikuac.shiro.annotation.GroupMessageHandler;
import com.mikuac.shiro.annotation.MessageHandlerFilter;
import com.mikuac.shiro.annotation.PrivateMessageHandler;
import com.mikuac.shiro.annotation.common.Shiro;
import com.mikuac.shiro.common.utils.MsgUtils;
import com.mikuac.shiro.core.Bot;
import com.mikuac.shiro.dto.event.message.*;
import com.mikuac.shiro.enums.AtEnum;

import ch.qos.logback.core.boolex.Matcher;
import jakarta.annotation.Resource;
import java.time.LocalDateTime;
import xyz.xingfeng.tingfeng.entity.GroupMessage;
import xyz.xingfeng.tingfeng.mapper.GroupMessageMapper;
import xyz.xingfeng.tingfeng.cq.CqCodeParser;
import xyz.xingfeng.tingfeng.cq.CqSegment;
import xyz.xingfeng.tingfeng.cq.MessageSegment;
import java.util.List;

@Shiro
@Component
public class Listen {
    @Resource
    private GroupMessageMapper groupMessageMapper;
    /**
     * 监听群信息
     */
    @GroupMessageHandler
    public void fun2(GroupMessageEvent event) {
        List<MessageSegment> segments = handleGroupMessage(event);
        System.out.println(segments);
        // GroupMessage msg = new GroupMessage();
        // msg.setGroupId(event.getGroupId());
        // msg.setSenderQq(event.getUserId());
        // msg.setSenderNickname(event.getSender().getNickname());
        // msg.setContent(event.getMessage());
        // msg.setSendTime(LocalDateTime.now());
        // groupMessageMapper.insert(msg);
    }

    /**
     * 处理群消息
     */
    public List<MessageSegment> handleGroupMessage(GroupMessageEvent event) {
        CqCodeParser parser = new CqCodeParser();
        List<MessageSegment> segments = parser.parse(event.getMessage());
        for (MessageSegment seg : segments) {
            if (seg.isCq()) {
                // 是什么类型的CQ码
                switch(seg.getCqSegment().getType()){
                    case "at":
                        // @某人
                        break;
                    case "image":
                        // 图片
                        // 是表情包还是普通图片
                        String subType = seg.getCqSegment().getData().get("sub_type");
                        if("1".equals(subType)){
                            // 表情包
                            seg.setText("我是经过模型处理的表情包");
                        }else{
                            // 普通图片
                            seg.setText("我是经过模型处理的普通图片");
                        }
                        break;
                    case "record":
                        // 语音
                        break;
                    case "face":
                        // 表情
                        break;
                    case "share":
                        // 分享
                        break;
                    case "music":
                        // 音乐
                        break;
                    case "reply":
                        // 回复
                        break;
                    case "forward":
                        // 合并转发
                        break;
                    default:
                        // 其他CQ码
                        break;  
                }
            }
        }
        return segments;
    }
}
