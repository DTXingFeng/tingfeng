package xyz.xingfeng.tingfeng;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.mybatis.spring.annotation.MapperScan;

@SpringBootApplication
@MapperScan("xyz.xingfeng.tingfeng.mapper")
public class TingfengApplication {

	public static void main(String[] args) {
		SpringApplication.run(TingfengApplication.class, args);
	}

}
