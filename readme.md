# TraceBoard——一个统计键盘使用情况的小工具

## 现有功能

* 可视化键盘按键使用情况

![img.png](doc/image/img.png)

## 待开发功能

* 常用按键情况
* 时间统计分析

## 使用

Windows用户可以直接[点击下载](https://github.com/LC044/TraceBoard/releases)exe可执行文件，直接双击就能运行。其他系统用户可以自行编译(运行)源码。

### 安装依赖

```bash
pip install -r requirements.txt
```
```bash
pip install win10toast
```
在3.10或更低版本的python时需要`pip install toml`

### 运行main.py

```bash
python main.py
```
### 升级数据库

如果是从旧版本升级到新版本，需要升级数据库。可以在命令行中执行以下命令：

```bash
python upgrade_db.py
```


## 感谢

[键盘UI](https://yanyunfeng.com/article/41)

## 改动说明

添加了一个配置文件来关闭启动时自动打开网页,或者使用windows通知来提示启动状态
[原项目地址](https://github.com/LC044/TraceBoard)
将数据库拆分为多个表，分别存储按键记录、总计信息,减少卡顿