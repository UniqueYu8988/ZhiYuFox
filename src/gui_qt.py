# -*- coding: utf-8 -*-
"""PySide6 客户端界面。"""

from __future__ import annotations

import ctypes
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
RESOURCE_ROOT = getattr(sys, "_MEIPASS", PROJECT_ROOT)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import bilibili_api
import config
import minimax_client
from app_service import SaveOptions, SaveResult, save_bilibili_video


ICON_PATH = os.path.join(RESOURCE_ROOT, "assets", "app_icon.ico")
APP_USER_MODEL_ID = "ProfessorZhi.BiliArchive"


def _short_message(message: str, limit: int = 120) -> str:
    normalized = " ".join((message or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..." if limit > 3 else normalized[:limit]


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def _resolve_login_state_text(settings: dict[str, str]) -> str:
    sessdata = (settings.get("sessdata") or "").strip()
    if not sessdata:
        return "未登录"
    ok, message = bilibili_api.validate_sessdata(sessdata)
    return message if ok else f"异常：{message}"


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("客户端设置")
        self.setModal(True)
        self.resize(760, 460)

        settings = config.get_runtime_settings()

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.sessdata_input = QLineEdit(settings.get("sessdata", ""))
        self.sessdata_input.setPlaceholderText("只填浏览器 Cookie 里的 SESSDATA 值")
        self.sessdata_input.setEchoMode(QLineEdit.PasswordEchoOnEdit)

        output_row = QHBoxLayout()
        self.output_input = QLineEdit(settings["output_dir"])
        self.output_input.setPlaceholderText("所有 Markdown 都会统一保存到这个目录")
        browse_button = QPushButton("选择...")
        browse_button.clicked.connect(self.choose_output_dir)
        output_row.addWidget(self.output_input, 1)
        output_row.addWidget(browse_button)

        self.api_key_input = QLineEdit(settings["minimax_api_key"])
        self.api_key_input.setPlaceholderText("留空则跳过 AI 总结")
        self.api_key_input.setEchoMode(QLineEdit.PasswordEchoOnEdit)

        self.model_input = QLineEdit(settings["minimax_model"])
        self.model_input.setPlaceholderText("例如：MiniMax-M2.7")

        self.sessdata_status_label = QLabel("尚未检测")
        self.api_status_label = QLabel("尚未检测")
        for label in (self.sessdata_status_label, self.api_status_label):
            label.setWordWrap(True)
            label.setStyleSheet("color: #5f6b7a;")

        form.addRow("SESSDATA", self.sessdata_input)
        form.addRow("SESSDATA 检测", self.sessdata_status_label)
        form.addRow("输出文件夹", output_row)
        form.addRow("MiniMax API Key", self.api_key_input)
        form.addRow("API 检测", self.api_status_label)
        form.addRow("MiniMax 模型", self.model_input)
        layout.addLayout(form)

        detect_row = QHBoxLayout()
        detect_row.addStretch(1)
        self.detect_button = QPushButton("立即检测")
        self.detect_button.clicked.connect(self.run_validation)
        detect_row.addWidget(self.detect_button)
        layout.addLayout(detect_row)

        help_text = QLabel(
            "说明：\n"
            "1. 登录只保留 SESSDATA 一种方式。\n"
            "2. SESSDATA 和 API Key 只保存在本地 .biliarchive.local.json，不会写进源码。\n"
            "3. 该本地文件默认已被 .gitignore 忽略。"
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #5f6b7a;")
        layout.addWidget(help_text)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            self.output_input.text().strip() or config.get_output_dir(),
        )
        if directory:
            self.output_input.setText(directory)

    def run_validation(self) -> tuple[bool, bool]:
        sessdata = self.sessdata_input.text().strip()
        api_key = self.api_key_input.text().strip()
        model = self.model_input.text().strip() or "MiniMax-M2.7"

        sess_ok, sess_message = bilibili_api.validate_sessdata(sessdata)
        api_ok, api_message = minimax_client.validate_api_key(api_key, model)

        self.sessdata_status_label.setText(sess_message)
        self.sessdata_status_label.setStyleSheet(f"color: {'#1f7a1f' if sess_ok else '#c0392b'};")
        self.api_status_label.setText(api_message)
        self.api_status_label.setStyleSheet(f"color: {'#1f7a1f' if api_ok else '#c0392b'};")
        return sess_ok, api_ok

    def accept(self) -> None:
        output_dir = self.output_input.text().strip() or config.DEFAULT_OUTPUT_DIR
        sessdata = self.sessdata_input.text().strip()
        api_key = self.api_key_input.text().strip()
        model = self.model_input.text().strip() or "MiniMax-M2.7"

        sess_ok, api_ok = self.run_validation()

        if sessdata and not sess_ok:
            QMessageBox.warning(self, "登录信息无效", "SESSDATA 检测未通过，请检查后再保存。")
            return
        if not api_ok:
            QMessageBox.warning(self, "API 设置无效", "MiniMax API Key 或模型检测未通过，请检查后再保存。")
            return

        config.save_runtime_settings(sessdata, output_dir, api_key, model)
        super().accept()


class SaveWorker(QThread):
    progress = Signal(str, int)
    success = Signal(object)
    failure = Signal(str)

    def __init__(self, video_input: str, options: SaveOptions):
        super().__init__()
        self.video_input = video_input
        self.options = options

    def run(self) -> None:
        try:
            result = save_bilibili_video(
                self.video_input,
                options=self.options,
                progress_callback=self.progress.emit,
            )
        except Exception as exc:
            self.failure.emit(str(exc))
            return
        self.success.emit(result)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker: SaveWorker | None = None
        self.last_output_dir = ""
        self.setWindowTitle(config.APP_NAME)
        self.resize(900, 720)
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))
        self._build_ui()
        self._refresh_settings_hint()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("输入 Bilibili 视频链接或 BV 号")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #1d232f;")
        layout.addWidget(title)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setTextFormat(Qt.PlainText)
        self.hint.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.hint.setStyleSheet("color: #5f6b7a;")
        layout.addWidget(self.hint)

        input_row = QHBoxLayout()
        self.video_input = QLineEdit()
        self.video_input.setPlaceholderText("例如：BV1xx411c7mD 或 https://www.bilibili.com/video/BV...")
        self.start_button = QPushButton("开始保存")
        self.start_button.clicked.connect(self.start_save)
        input_row.addWidget(self.video_input, 1)
        input_row.addWidget(self.start_button)
        layout.addLayout(input_row)

        options_row = QHBoxLayout()
        self.ai_checkbox = QCheckBox("生成 AI 总结")
        self.ai_checkbox.setChecked(True)

        self.settings_button = QPushButton("客户端设置")
        self.settings_button.clicked.connect(self.open_settings)

        options_row.addWidget(self.ai_checkbox)
        options_row.addWidget(self.settings_button)
        options_row.addStretch(1)
        layout.addLayout(options_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: none;
                border-radius: 3px;
                background: #e8eef6;
            }
            QProgressBar::chunk {
                border-radius: 3px;
                background: #2f7cf6;
            }
            """
        )
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("状态：等待输入")
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.PlainText)
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.status_label.setStyleSheet("color: #0f5c8a;")
        layout.addWidget(self.status_label)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.title_value = QLineEdit()
        self.title_value.setReadOnly(True)
        self.date_value = QLineEdit()
        self.date_value.setReadOnly(True)
        self.output_value = QLineEdit()
        self.output_value.setReadOnly(True)
        self.markdown_value = QLineEdit()
        self.markdown_value.setReadOnly(True)

        form.addRow("视频标题", self.title_value)
        form.addRow("发布日期", self.date_value)
        form.addRow("输出目录", self.output_value)
        form.addRow("Markdown 文件", self.markdown_value)
        layout.addLayout(form)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self.open_button = QPushButton("打开输出目录")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_output_dir)
        action_row.addWidget(self.open_button)
        layout.addLayout(action_row)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.log_output.setPlaceholderText("运行日志会显示在这里...")
        layout.addWidget(self.log_output, 1)

    def _refresh_settings_hint(self) -> None:
        settings = config.get_runtime_settings()
        login_state = _resolve_login_state_text(settings)
        self.hint.setText(
            f"当前会输出精简 Markdown，只保留标题、日期和 AI 总结。输出目录：{settings['output_dir']}；B站状态：{login_state}。"
        )

    def open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec():
            self._refresh_settings_hint()
            QMessageBox.information(self, "保存成功", "本地设置已保存，不会写入源码。")

    def start_save(self) -> None:
        video_input = self.video_input.text().strip()
        if not video_input:
            QMessageBox.warning(self, "缺少输入", "请输入 BV 号或视频链接。")
            return
        if self.worker and self.worker.isRunning():
            return

        options = SaveOptions(
            generate_summary=self.ai_checkbox.isChecked(),
        )

        self._set_busy(True)
        self._clear_result()
        self._update_progress("开始处理视频...", 1)
        self.worker = SaveWorker(video_input, options)
        self.worker.progress.connect(self.on_progress)
        self.worker.success.connect(self.on_success)
        self.worker.failure.connect(self.on_failure)
        self.worker.start()

    def on_progress(self, message: str, value: int) -> None:
        self._update_progress(message, value)

    def on_success(self, result: SaveResult) -> None:
        self.title_value.setText(result.video_title)
        self.date_value.setText(result.publish_date)
        self.output_value.setText(result.output_dir)
        self.markdown_value.setText(result.markdown_path)
        self.last_output_dir = result.output_dir
        self.open_button.setEnabled(True)

        self.log_output.appendPlainText(
            f"字幕来源：{result.subtitle_source_type}（{result.subtitle_source_api}）"
        )
        self.log_output.appendPlainText(f"字幕说明：{result.subtitle_note}")
        self.status_label.setText("状态：处理完成，Markdown 已生成。")
        self.progress_bar.setValue(100)
        self._set_busy(False)

    def on_failure(self, message: str) -> None:
        self._update_progress(f"处理失败：{message}", 100)
        QMessageBox.critical(self, "处理失败", _short_message(message, 300))
        self._set_busy(False)

    def _update_progress(self, message: str, value: int) -> None:
        self.log_output.appendPlainText(message)
        self.status_label.setText(f"状态：{_short_message(message, 160)} ({value}%)")
        self.progress_bar.setValue(max(0, min(value, 100)))

    def open_output_dir(self) -> None:
        if not self.last_output_dir or not os.path.isdir(self.last_output_dir):
            QMessageBox.information(self, "目录不存在", "当前没有可打开的输出目录。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_output_dir))

    def _set_busy(self, busy: bool) -> None:
        self.start_button.setEnabled(not busy)
        self.video_input.setEnabled(not busy)
        self.ai_checkbox.setEnabled(not busy)
        self.settings_button.setEnabled(not busy)

    def _clear_result(self) -> None:
        self.title_value.clear()
        self.date_value.clear()
        self.output_value.clear()
        self.markdown_value.clear()
        self.open_button.setEnabled(False)
        self.last_output_dir = ""
        self.log_output.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("状态：等待输入")


def run_gui() -> None:
    _set_windows_app_id()
    app = QApplication(sys.argv)
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    run_gui()
