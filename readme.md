# TraceBoard  
一个用于 **统计与可视化键盘使用情况** 的 Windows 工具

TraceBoard 会在后台监听键盘输入，并将统计结果以 **热力图、时间轴、快捷键统计** 等形式展示，帮助你了解自己的键盘使用习惯。

---

## ✨ 当前已实现功能

### ⌨️ 按键使用统计
- 每个按键的 **累计使用次数**
- 键盘 UI 实时高亮，颜色随使用频率变化

### 📅 Activity Heatmap（活跃度热力图）
- **最近 120 天**：按天统计按键次数（日历热力图）
- **最近 24 小时**：按小时统计使用情况（小时热力图）
- 两种热力图 **同时显示**，无需切换

### 🧩 快捷键统计（Hotkeys）
- 统计快捷键（如 `Ctrl+C / Ctrl+V / Alt+Tab`）触发次数
- 支持：
  - 单个快捷键的每日热力图
  - **“全部快捷键”汇总视图**
- 自动去重、不会重复计数

### 🗃️ 重新设计数据库
- 不再存储逐条按键事件
- 使用 **聚合表** 存储：
  - 按键总计
  - 按日 / 按月 / 按小时统计
  - 快捷键总计 / 每日统计
- 避免数据库无限膨胀，长时间运行不卡顿

### ⚙️ 后台运行
- 后台监听键盘
- 可配置：
  - 启动时是否自动打开网页
  - 是否使用 Windows 通知提示启动状态

---

## 🖼️ 界面预览

![img.png](doc/image/img.png)

---

## 🚀 使用方式


#### 1️⃣ 安装依赖

```bash
pip install -r requirements.txt
pip install win10toast
```

> Python 3.10 或更低版本需要额外安装：
```bash
pip install toml
```

#### 2️⃣ 运行程序

```bash
python main.py
```

---

## 🗄️ 数据库升级说明

如果你是 **从旧版本升级**，必须先升级数据库结构。

```bash
python upgrade_db_v3.py your_database.db
```

如果确认不再需要旧表：

```bash
python upgrade_db_v3.py your_database.db --drop-old
```

---

## 🧠 架构说明

```
键盘监听
   ↓
内存缓冲
   ↓
SQLite 聚合表
   ↓
FastAPI 接口
   ↓
前端 Dashboard
```

---

## 致谢

[键盘UI](https://yanyunfeng.com/article/41)
[原项目地址](https://github.com/LC044/TraceBoard)

---

## 📝 改动说明（相对原版）

1. 重构键盘监听与统计逻辑，解决长时间运行卡顿  
2. 数据库拆分为多张聚合表，避免逐条事件爆炸  
3. 新增最近 24 小时热力图与快捷键统计  
4. 提升整体稳定性与可维护性