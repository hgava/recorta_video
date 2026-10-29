import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import cv2
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from PIL import Image, ImageTk


class VideoTrimmerTk:

    def __init__(self, root):
        self.root = root
        self.root.title("Cortador de Vídeo MP4")
        self.root.geometry("820x680")
        self.root.configure(bg="#1e1e1e")

        self.video_path = ""
        self.cap = None
        self.fps = 30.0
        self.total_frames = 0
        self.duration_sec = 0.0
        self.is_playing = False

        self.start_sec = 0.0
        self.end_sec = 0.0

        self.criar_interface()

    def criar_interface(self):
        # Botão Abrir
        self.btn_open = tk.Button(
            self.root,
            text="📁 Abrir Vídeo (.mp4)",
            bg="#2d3748",
            fg="white",
            font=("Arial", 10, "bold"),
            command=self.abrir_video,
        )
        self.btn_open.pack(fill=tk.X, padx=12, pady=8)

        # Canvas de Vídeo
        self.canvas = tk.Canvas(self.root, bg="#000000", width=760, height=420)
        self.canvas.pack(padx=12, pady=4, expand=True)

        # Barra do Tempo
        self.scale_time = tk.Scale(
            self.root,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            showvalue=0,
            bg="#1e1e1e",
            fg="white",
            troughcolor="#374151",
            command=self.ao_arrastar_barra,
        )
        self.scale_time.pack(fill=tk.X, padx=12, pady=4)

        # Labels de Início / Posição / Fim
        frame_labels = tk.Frame(self.root, bg="#1e1e1e")
        frame_labels.pack(fill=tk.X, padx=12)

        self.lbl_start = tk.Label(
            frame_labels,
            text="Início: 00:00:00",
            bg="#1e1e1e",
            fg="#60a5fa",
            font=("Arial", 9, "bold"),
        )
        self.lbl_start.pack(side=tk.LEFT)

        self.lbl_current = tk.Label(
            frame_labels,
            text="00:00:00 / 00:00:00",
            bg="#1e1e1e",
            fg="white",
            font=("Arial", 9),
        )
        self.lbl_current.pack(side=tk.LEFT, expand=True)

        self.lbl_end = tk.Label(
            frame_labels,
            text="Fim: 00:00:00",
            bg="#1e1e1e",
            fg="#f87171",
            font=("Arial", 9, "bold"),
        )
        self.lbl_end.pack(side=tk.RIGHT)

        # Controlos de Corte e Reprodução
        frame_ctrl = tk.Frame(self.root, bg="#1e1e1e")
        frame_ctrl.pack(fill=tk.X, padx=12, pady=8)

        self.btn_play = tk.Button(
            frame_ctrl,
            text="▶ Play",
            bg="#374151",
            fg="white",
            width=8,
            command=self.alternar_play,
        )
        self.btn_play.pack(side=tk.LEFT, padx=4)

        self.btn_mark_in = tk.Button(
            frame_ctrl,
            text="✂ Início Aqui",
            bg="#1e3a8a",
            fg="white",
            command=self.marcar_inicio,
        )
        self.btn_mark_in.pack(side=tk.LEFT, padx=4)

        self.btn_mark_out = tk.Button(
            frame_ctrl,
            text="✂ Fim Aqui",
            bg="#7f1d1d",
            fg="white",
            command=self.marcar_fim,
        )
        self.btn_mark_out.pack(side=tk.LEFT, padx=4)

        # Botão Confirmar Recorte
        self.btn_save = tk.Button(
            self.root,
            text="Confirmar Recorte",
            bg="#dc2626",
            fg="white",
            font=("Arial", 11, "bold"),
            height=2,
            command=self.salvar_recorte,
        )
        self.btn_save.pack(fill=tk.X, padx=12, pady=8)

    def formatar_tempo(self, segundos):
        s = int(segundos)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def abrir_video(self):
        caminho = filedialog.askopenfilename(
            filetypes=[("Vídeos MP4", "*.mp4")]
        )
        if not caminho:
            return

        self.video_path = caminho
        if self.cap:
            self.cap.release()

        self.cap = cv2.VideoCapture(self.video_path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration_sec = (
            self.total_frames / self.fps if self.fps > 0 else 0.0
        )

        self.scale_time.config(to=self.total_frames)
        self.start_sec = 0.0
        self.end_sec = self.duration_sec

        self.lbl_start.config(text=f"Início: {self.formatar_tempo(0)}")
        self.lbl_end.config(
            text=f"Fim: {self.formatar_tempo(self.duration_sec)}"
        )
        self.exibir_frame(0)

    def exibir_frame(self, frame_num):
        if not self.cap:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame.shape[:2]

            # Redimensionamento proporcional ao Canvas
            cw, ch = 760, 420
            ratio = min(cw / w, ch / h)
            nw, nh = int(w * ratio), int(h * ratio)

            frame = cv2.resize(frame, (nw, nh))
            img = ImageTk.PhotoImage(image=Image.fromarray(frame))
            self.canvas.delete("all")
            self.canvas.create_image(cw // 2, ch // 2, anchor=tk.CENTER, image=img)
            self.canvas.image = img

            seg_atual = frame_num / self.fps
            self.lbl_current.config(
                text=f"{self.formatar_tempo(seg_atual)} / {self.formatar_tempo(self.duration_sec)}"
            )

    def ao_arrastar_barra(self, val):
        if not self.is_playing:
            self.exibir_frame(int(val))

    def marcar_inicio(self):
        pos = self.scale_time.get()
        self.start_sec = pos / self.fps
        self.lbl_start.config(
            text=f"Início: {self.formatar_tempo(self.start_sec)}"
        )

    def marcar_fim(self):
        pos = self.scale_time.get()
        self.end_sec = pos / self.fps
        self.lbl_end.config(text=f"Fim: {self.formatar_tempo(self.end_sec)}")

    def alternar_play(self):
        self.is_playing = not self.is_playing
        self.btn_play.config(text="⏸ Pausa" if self.is_playing else "▶ Play")
        if self.is_playing:
            self.loop_video()

    def loop_video(self):
        if not self.is_playing or not self.cap:
            return
        atual = self.scale_time.get() + 1
        if atual >= self.total_frames:
            self.is_playing = False
            self.btn_play.config(text="▶ Play")
            return

        self.scale_time.set(atual)
        self.exibir_frame(atual)
        self.root.after(int(1000 / self.fps), self.loop_video)

    def gerar_caminho_saida(self):
        pasta = os.path.dirname(self.video_path)
        base, ext = os.path.splitext(os.path.basename(self.video_path))
        i = 1
        while True:
            novo = os.path.join(pasta, f"{base}_recorte{i}{ext}")
            if not os.path.exists(novo):
                return novo
            i += 1

    def salvar_recorte(self):
        if not self.video_path:
            return
        if self.start_sec >= self.end_sec:
            messagebox.showwarning(
                "Aviso", "O início tem de ser menor do que o fim."
            )
            return

        if self.is_playing:
            self.alternar_play()

        saida = self.gerar_caminho_saida()
        self.btn_save.config(text="A processar...", state=tk.DISABLED)
        self.root.update()

        try:
            ffmpeg_extract_subclip(
                self.video_path, self.start_sec, self.end_sec, targetname=saida
            )
            messagebox.showinfo(
                "Sucesso", f"Guardado com sucesso:\n{os.path.basename(saida)}"
            )
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao cortar vídeo:\n{e}")
        finally:
            self.btn_save.config(text="Confirmar Recorte", state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoTrimmerTk(root)
    root.mainloop()