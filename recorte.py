import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import cv2
from PIL import Image, ImageTk

# Importação compatível com qualquer versão do moviepy
try:
    from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
except ImportError:
    try:
        from moviepy.tools import ffmpeg_extract_subclip
    except ImportError:
        ffmpeg_extract_subclip = None


class CustomTrimBar(tk.Canvas):
    """Barra superior com dois marcadores deslizantes."""

    def __init__(self, parent, on_change_callback=None, **kwargs):
        super().__init__(
            parent,
            height=36,
            bg="#2b2b2b",
            highlightthickness=0,
            cursor="hand2",
            **kwargs,
        )
        self.on_change = on_change_callback
        self.total_duration = 1.0
        self.start_ratio = 0.0
        self.end_ratio = 1.0
        self.active_drag = None

        self.bind("<Configure>", lambda e: self.desenhar())
        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)

    def set_duracao(self, duracao):
        self.total_duration = max(duracao, 0.1)
        self.start_ratio = 0.0
        self.end_ratio = 1.0
        self.desenhar()

    def desenhar(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 40:
            return

        pad = 16
        track_w = w - (2 * pad)
        cy = h // 2

        self.create_rectangle(
            pad, cy - 6, w - pad, cy + 6, fill="#3f3f3f", outline=""
        )

        x1 = pad + int(self.start_ratio * track_w)
        x2 = pad + int(self.end_ratio * track_w)
        self.create_rectangle(x1, cy - 6, x2, cy + 6, fill="#525252", outline="")

        self.create_rectangle(
            x1 - 8, 4, x1 + 8, h - 4, fill="#f3f4f6", outline="#9ca3af", width=1
        )
        self.create_line(x1 - 2, 9, x1 - 2, h - 9, fill="#6b7280")
        self.create_line(x1 + 2, 9, x1 + 2, h - 9, fill="#6b7280")

        self.create_rectangle(
            x2 - 8, 4, x2 + 8, h - 4, fill="#f3f4f6", outline="#9ca3af", width=1
        )
        self.create_line(x2 - 2, 9, x2 - 2, h - 9, fill="#6b7280")
        self.create_line(x2 + 2, 9, x2 + 2, h - 9, fill="#6b7280")

    def get_pos_ratio(self, x):
        pad = 16
        track_w = max(self.winfo_width() - (2 * pad), 1)
        ratio = (x - pad) / track_w
        return max(0.0, min(1.0, ratio))

    def on_click(self, event):
        pad = 16
        track_w = self.winfo_width() - (2 * pad)
        x1 = pad + (self.start_ratio * track_w)
        x2 = pad + (self.end_ratio * track_w)

        d1 = abs(event.x - x1)
        d2 = abs(event.x - x2)

        self.active_drag = "start" if d1 < d2 else "end"
        self.on_drag(event)

    def on_drag(self, event):
        ratio = self.get_pos_ratio(event.x)
        if self.active_drag == "start":
            self.start_ratio = min(ratio, self.end_ratio - 0.005)
        elif self.active_drag == "end":
            self.end_ratio = max(ratio, self.start_ratio + 0.005)

        self.desenhar()
        if self.on_change:
            self.on_change(
                self.start_ratio * self.total_duration,
                self.end_ratio * self.total_duration,
            )

    def on_release(self, event):
        self.active_drag = None


class VideoTrimmerApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Recorte de Vídeo")
        self.root.geometry("900x700")
        self.root.minsize(700, 520)
        self.root.configure(bg="#1c1c1c")

        self.video_path = ""
        self.cap = None
        self.fps = 30.0
        self.total_frames = 0
        self.duration_sec = 0.0
        self.current_frame = 0
        self.is_playing = False

        self.start_sec = 0.0
        self.end_sec = 0.0

        self.setup_ui()

    def formatar_tempo(self, segundos):
        s = int(segundos)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def setup_ui(self):
        bar_top = tk.Frame(self.root, bg="#1c1c1c", pady=4)
        bar_top.pack(fill=tk.X, padx=12)

        btn_select = tk.Button(
            bar_top,
            text="📂 Abrir Vídeo (.mp4)",
            bg="#2a2a2a",
            fg="#e5e7eb",
            relief="flat",
            activebackground="#3f3f3f",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            padx=14,
            pady=4,
            cursor="hand2",
            command=self.abrir_arquivo,
        )
        btn_select.pack(side=tk.LEFT)

        self.trim_bar = CustomTrimBar(
            self.root, on_change_callback=self.on_trim_slider_change
        )
        self.trim_bar.pack(fill=tk.X, padx=14, pady=(6, 0))

        lbl_box = tk.Frame(self.root, bg="#1c1c1c")
        lbl_box.pack(fill=tk.X, padx=18, pady=(2, 6))

        self.lbl_start = tk.Label(
            lbl_box,
            text="00:00:00",
            bg="#1c1c1c",
            fg="#d1d5db",
            font=("Consolas", 10),
        )
        self.lbl_start.pack(side=tk.LEFT)

        self.lbl_end = tk.Label(
            lbl_box,
            text="00:00:00",
            bg="#1c1c1c",
            fg="#d1d5db",
            font=("Consolas", 10),
        )
        self.lbl_end.pack(side=tk.RIGHT)

        self.video_frame = tk.Frame(self.root, bg="#000000")
        self.video_frame.pack(fill=tk.BOTH, expand=True, padx=14)

        self.canvas_video = tk.Canvas(
            self.video_frame, bg="#000000", highlightthickness=0
        )
        self.canvas_video.pack(fill=tk.BOTH, expand=True)

        player_nav = tk.Frame(self.root, bg="#262626")
        player_nav.pack(fill=tk.X, padx=14, pady=(6, 0))

        self.slider_play = tk.Scale(
            player_nav,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            showvalue=0,
            bg="#262626",
            fg="#ffffff",
            troughcolor="#3d3d3d",
            activebackground="#60a5fa",
            highlightthickness=0,
            bd=0,
            command=self.on_scrub,
        )
        self.slider_play.pack(fill=tk.X, padx=10, pady=3)

        ctrl_bar = tk.Frame(self.root, bg="#363636", height=42)
        ctrl_bar.pack(fill=tk.X, padx=14, pady=(0, 8))

        self.btn_play = tk.Button(
            ctrl_bar,
            text="▶",
            bg="#363636",
            fg="#ffffff",
            activebackground="#4a4a4a",
            activeforeground="#ffffff",
            relief="flat",
            font=("Segoe UI", 12, "bold"),
            width=4,
            cursor="hand2",
            command=self.alternar_play,
        )
        self.btn_play.pack(side=tk.LEFT, padx=(6, 2), pady=4)

        self.btn_preview_sel = tk.Button(
            ctrl_bar,
            text="✂ Testar Recorte",
            bg="#444444",
            fg="#ffffff",
            activebackground="#555555",
            activeforeground="#ffffff",
            relief="flat",
            font=("Segoe UI", 9),
            padx=8,
            cursor="hand2",
            command=self.play_selecao,
        )
        self.btn_preview_sel.pack(side=tk.LEFT, padx=6)

        self.lbl_clock = tk.Label(
            ctrl_bar,
            text="00:00:00 / 00:00:00",
            bg="#363636",
            fg="#e5e7eb",
            font=("Consolas", 10),
        )
        self.lbl_clock.pack(side=tk.LEFT, padx=12)

        footer = tk.Frame(self.root, bg="#1c1c1c", height=54)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        # Corrigido: destroy sem parênteses na chamada para não fechar logo ao arrancar
        self.btn_cancel = tk.Button(
            footer,
            text="Cancelar",
            bg="#d2d5da",
            fg="#1f2937",
            activebackground="#b9bcc2",
            activeforeground="#111827",
            relief="flat",
            font=("Segoe UI", 11, "bold"),
            cursor="hand2",
            command=self.fechar_aplicacao,
        )
        self.btn_cancel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.btn_confirm = tk.Button(
            footer,
            text="Confirmar",
            bg="#db3d4d",
            fg="#ffffff",
            activebackground="#b92d3c",
            activeforeground="#ffffff",
            relief="flat",
            font=("Segoe UI", 11, "bold"),
            cursor="hand2",
            command=self.salvar_recorte,
        )
        self.btn_confirm.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    def fechar_aplicacao(self):
        if self.cap:
            self.cap.release()
        self.root.destroy()

    def on_trim_slider_change(self, inicio, fim):
        self.start_sec = inicio
        self.end_sec = fim
        self.lbl_start.config(text=self.formatar_tempo(inicio))
        self.lbl_end.config(text=self.formatar_tempo(fim))

    def abrir_arquivo(self):
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
            self.total_frames / self.fps if self.fps > 0 else 0.1
        )

        self.trim_bar.set_duracao(self.duration_sec)
        self.slider_play.config(to=self.total_frames)

        self.start_sec = 0.0
        self.end_sec = self.duration_sec
        self.lbl_start.config(text=self.formatar_tempo(0))
        self.lbl_end.config(text=self.formatar_tempo(self.duration_sec))

        self.mostrar_frame(0)

    def mostrar_frame(self, frame_num):
        if not self.cap:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame.shape[:2]

            cw = max(self.canvas_video.winfo_width(), 400)
            ch = max(self.canvas_video.winfo_height(), 260)

            ratio = min(cw / w, ch / h)
            nw, nh = max(int(w * ratio), 1), max(int(h * ratio), 1)

            frame = cv2.resize(frame, (nw, nh))
            img = ImageTk.PhotoImage(image=Image.fromarray(frame))

            self.canvas_video.delete("all")
            self.canvas_video.create_image(
                cw // 2, ch // 2, anchor=tk.CENTER, image=img
            )
            self.canvas_video.image = img

            sec_atual = frame_num / self.fps
            self.lbl_clock.config(
                text=f"{self.formatar_tempo(sec_atual)} / {self.formatar_tempo(self.duration_sec)}"
            )

    def on_scrub(self, val):
        if not self.is_playing:
            self.current_frame = int(val)
            self.mostrar_frame(self.current_frame)

    def alternar_play(self):
        self.is_playing = not self.is_playing
        self.btn_play.config(text="⏸" if self.is_playing else "▶")
        if self.is_playing:
            self.loop_video()

    def play_selecao(self):
        if not self.cap:
            return
        self.current_frame = int(self.start_sec * self.fps)
        self.slider_play.set(self.current_frame)
        self.mostrar_frame(self.current_frame)
        self.is_playing = True
        self.btn_play.config(text="⏸")
        self.loop_video(preview_mode=True)

    def loop_video(self, preview_mode=False):
        if not self.is_playing or not self.cap:
            return

        self.current_frame += 1
        limite = (
            int(self.end_sec * self.fps) if preview_mode else self.total_frames
        )

        if self.current_frame >= limite:
            self.is_playing = False
            self.btn_play.config(text="▶")
            return

        self.slider_play.set(self.current_frame)
        self.mostrar_frame(self.current_frame)
        self.root.after(
            int(1000 / self.fps), lambda: self.loop_video(preview_mode)
        )

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
                "Aviso", "O tempo de início deve ser menor que o de fim."
            )
            return

        if self.is_playing:
            self.alternar_play()

        saida = self.gerar_caminho_saida()
        self.btn_confirm.config(text="A guardar...", state=tk.DISABLED)
        self.root.update()

        try:
            try:
                ffmpeg_extract_subclip(
                    self.video_path, self.start_sec, self.end_sec, saida
                )
            except TypeError:
                ffmpeg_extract_subclip(
                    self.video_path,
                    self.start_sec,
                    self.end_sec,
                    outputfile=saida,
                )

            messagebox.showinfo(
                "Concluído",
                f"Recorte guardado com sucesso!\n\nFicheiro:\n{os.path.basename(saida)}",
            )
        except Exception as e:
            messagebox.showerror(
                "Erro", f"Falha ao realizar recorte:\n{e}"
            )  #[cite: 3]
        finally:
            self.btn_confirm.config(text="Confirmar", state=tk.NORMAL)


if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = VideoTrimmerApp(root)
        root.mainloop()
    except Exception as err:
        print(f"Erro detetado: {err}")
        input("Pressione Enter para sair...")