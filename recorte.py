import os
import sys
from PyQt5.QtCore import QTime, QUrl, Qt
from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip


class RangeSlider(QWidget):
    """Barra deslizante dupla para marcar Início e Fim do corte."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.min_val = 0
        self.max_val = 1000
        self.start_val = 0
        self.end_val = 1000
        self.active_handle = None
        self.setFixedHeight(30)

    def set_range(self, minimum, maximum):
        self.min_val = minimum
        self.max_val = max(maximum, 1)
        self.start_val = minimum
        self.end_val = maximum
        self.update()

    def set_start(self, val):
        self.start_val = max(self.min_val, min(val, self.end_val))
        self.update()

    def set_end(self, val):
        self.end_val = min(self.max_val, max(val, self.start_val))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()

        # Fundo da trilha
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(40, 40, 40))
        painter.drawRoundedRect(10, h // 2 - 4, w - 20, 8, 4, 4)

        # Região selecionada (verde escuro)
        total = self.max_val - self.min_val or 1
        x1 = 10 + int((self.start_val - self.min_val) / total * (w - 20))
        x2 = 10 + int((self.end_val - self.min_val) / total * (w - 20))

        painter.setBrush(QColor(70, 130, 180))
        painter.drawRect(x1, h // 2 - 4, x2 - x1, 8)

        # Marcador Início
        painter.setBrush(QColor(230, 230, 230))
        painter.drawRoundedRect(x1 - 6, 4, 12, h - 8, 3, 3)

        # Marcador Fim
        painter.setBrush(QColor(230, 230, 230))
        painter.drawRoundedRect(x2 - 6, 4, 12, h - 8, 3, 3)

    def mousePressEvent(self, event):
        w = self.width()
        total = self.max_val - self.min_val or 1
        pos_val = self.min_val + int((event.x() - 10) / (w - 20) * total)

        # Determina qual marcador está mais próximo
        d_start = abs(pos_val - self.start_val)
        d_end = abs(pos_val - self.end_val)

        if d_start < d_end:
            self.active_handle = "start"
            self.set_start(pos_val)
        else:
            self.active_handle = "end"
            self.set_end(pos_val)

    def mouseMoveEvent(self, event):
        if not self.active_handle:
            return
        w = self.width()
        total = self.max_val - self.min_val or 1
        pos_val = self.min_val + int((event.x() - 10) / (w - 20) * total)

        if self.active_handle == "start":
            self.set_start(pos_val)
        elif self.active_handle == "end":
            self.set_end(pos_val)

    def mouseReleaseEvent(self, event):
        self.active_handle = None


class VideoTrimmerApp(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cortador de Vídeo MP4")
        self.resize(850, 600)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")

        self.video_path = ""
        self.duration_ms = 0

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)

        # 1. Botão para Abrir Vídeo
        self.btn_open = QPushButton("Selecionar Vídeo (.mp4)")
        self.btn_open.setStyleSheet(
            "background-color: #333333; padding: 6px; font-weight: bold; border-radius: 4px;"
        )
        self.btn_open.clicked.connect(self.abrir_arquivo)
        main_layout.addWidget(self.btn_open)

        # 2. Player de Vídeo
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.video_widget = QVideoWidget()
        self.media_player.setVideoOutput(self.video_widget)
        main_layout.addWidget(self.video_widget, stretch=1)

        # 3. Faixa de Corte (Marcadores Superior)
        self.trim_slider = RangeSlider()
        main_layout.addWidget(self.trim_slider)

        # Labels de tempo de corte (Início / Fim)
        labels_layout = QHBoxLayout()
        self.lbl_start = QLabel("00:00:00")
        self.lbl_end = QLabel("00:00:00")
        labels_layout.addWidget(self.lbl_start)
        labels_layout.addStretch()
        labels_layout.addWidget(self.lbl_end)
        main_layout.addLayout(labels_layout)

        # 4. Linha do Tempo / Barra de Reprodução
        self.play_slider = QSlider(Qt.Horizontal)
        self.play_slider.setRange(0, 0)
        self.play_slider.sliderMoved.connect(self.set_posicao)
        main_layout.addWidget(self.play_slider)

        # 5. Controles de Reprodução
        controls_layout = QHBoxLayout()

        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_play.clicked.connect(self.alternar_play)
        controls_layout.addWidget(self.btn_play)

        self.lbl_current_time = QLabel("00:00:00 / 00:00:00")
        controls_layout.addWidget(self.lbl_current_time)
        controls_layout.addStretch()

        # Botões para fixar início e fim na posição atual da agulha
        btn_mark_in = QPushButton("✂ Definir Início Aqui")
        btn_mark_in.setStyleSheet("background-color: #2b2b2b; padding: 4px;")
        btn_mark_in.clicked.connect(self.marcar_inicio_atual)

        btn_mark_out = QPushButton("✂ Definir Fim Aqui")
        btn_mark_out.setStyleSheet("background-color: #2b2b2b; padding: 4px;")
        btn_mark_out.clicked.connect(self.marcar_fim_atual)

        controls_layout.addWidget(btn_mark_in)
        controls_layout.addWidget(btn_mark_out)

        main_layout.addLayout(controls_layout)

        # 6. Botões Inferiores (Cancelar e Confirmar/Cortar)
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(0)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setStyleSheet(
            "background-color: #d1d5db; color: #111111; font-weight: bold; height: 42px;"
        )
        self.btn_cancel.clicked.connect(self.close)

        self.btn_confirm = QPushButton("Confirmar Recorte")
        self.btn_confirm.setStyleSheet(
            "background-color: #dc3545; color: #ffffff; font-weight: bold; height: 42px;"
        )
        self.btn_confirm.clicked.connect(self.salvar_recorte)

        footer_layout.addWidget(self.btn_cancel)
        footer_layout.addWidget(self.btn_confirm)
        main_layout.addLayout(footer_layout)

        self.setLayout(main_layout)

        # Sinais do Media Player
        self.media_player.positionChanged.connect(self.posicao_alterada)
        self.media_player.durationChanged.connect(self.duracao_alterada)

    def abrir_arquivo(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Abrir Vídeo", "", "Vídeos (*.mp4)"
        )
        if caminho:
            self.video_path = caminho
            self.media_player.setMedia(
                QMediaContent(QUrl.fromLocalFile(caminho))
            )
            self.media_player.play()

    def alternar_play(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.SP_MediaPlay)
            )
        else:
            self.media_player.play()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.SP_MediaPause)
            )

    def set_posicao(self, pos):
        self.media_player.setPosition(pos)

    def posicao_alterada(self, pos):
        self.play_slider.setValue(pos)
        tempo_atual = self.formatar_tempo(pos)
        tempo_total = self.formatar_tempo(self.duration_ms)
        self.lbl_current_time.setText(f"{tempo_atual} / {tempo_total}")

    def duracao_alterada(self, duration):
        self.duration_ms = duration
        self.play_slider.setRange(0, duration)
        self.trim_slider.set_range(0, duration)
        self.lbl_start.setText("00:00:00")
        self.lbl_end.setText(self.formatar_tempo(duration))

    def marcar_inicio_atual(self):
        pos = self.media_player.position()
        self.trim_slider.set_start(pos)
        self.lbl_start.setText(self.formatar_tempo(self.trim_slider.start_val))

    def marcar_fim_atual(self):
        pos = self.media_player.position()
        self.trim_slider.set_end(pos)
        self.lbl_end.setText(self.formatar_tempo(self.trim_slider.end_val))

    def formatar_tempo(self, ms):
        segundos = int(ms / 1000)
        horas = segundos // 3600
        minutos = (segundos % 3600) // 60
        segs = segundos % 60
        return f"{horas:02d}:{minutos:02d}:{segs:02d}"

    def gerar_caminho_saida(self):
        pasta = os.path.dirname(self.video_path)
        nome_completo = os.path.basename(self.video_path)
        nome_base, ext = os.path.splitext(nome_completo)

        indice = 1
        while True:
            novo_nome = f"{nome_base}_recorte{indice}{ext}"
            caminho_final = os.path.join(pasta, novo_nome)
            if not os.path.exists(caminho_final):
                return caminho_final
            indice += 1

    def salvar_recorte(self):
        if not self.video_path:
            return

        t_inicio_seg = self.trim_slider.start_val / 1000.0
        t_fim_seg = self.trim_slider.end_val / 1000.0

        if t_inicio_seg >= t_fim_seg:
            QMessageBox.warning(
                self,
                "Atenção",
                "O tempo inicial precisa ser menor que o tempo final.",
            )
            return

        caminho_saida = self.gerar_caminho_saida()

        # Pausa o vídeo durante a exportação
        self.media_player.pause()
        self.btn_confirm.setEnabled(False)
        self.btn_confirm.setText("Salvando...")
        QApplication.processEvents()

        try:
            # Corte direto via ffmpeg (rápido e sem perda de qualidade)
            ffmpeg_extract_subclip(
                self.video_path, t_inicio_seg, t_fim_seg, targetname=caminho_saida
            )
            QMessageBox.information(
                self, "Sucesso", f"Salvo em:\n{caminho_saida}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Erro ao processar recorte:\n{e}"
            )
        finally:
            self.btn_confirm.setEnabled(True)
            self.btn_confirm.setText("Confirmar Recorte")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    janela = VideoTrimmerApp()
    janela.show()
    sys.exit(app.exec_())