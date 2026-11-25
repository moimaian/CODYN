# -*- coding: utf-8 -*-
"""Widgets reutilizáveis do CODYN: grupo recolhível, console de log, rótulos e barras padrão."""

import re
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QFrame, QGroupBox, QLabel, QProgressBar, QTextEdit, QWidget,
)

from BIN.theme import PALETTE

_QtGroupBox = QGroupBox


class CollapsibleGroupBox(_QtGroupBox):
    """QGroupBox que colapsa/expande ao clicar no título (mesmo comportamento do CODRUG).
    Qualquer grupo com título pode iniciar colapsado via set_collapsed(True), o que reduz a altura
    que a janela precisa. Grupos sem título não colapsam (não há onde clicar).

    Ao colapsar, esconde só os widgets FILHOS DIRETOS do grupo (os aninhados somem junto, com o próprio
    estado de visibilidade preservado) e fixa a altura na do título; ao expandir, reexibe apenas os que
    estavam visíveis antes e restaura a altura mínima/máxima original (grupos com setFixedSize voltam
    ao tamanho certo). Um marcador (seta) no título indica o estado."""

    _ARROW_OPEN = "\u25BE "
    _ARROW_CLOSED = "\u25B8 "

    # Emitido só quando o USUÁRIO colapsa/expande clicando no título (não em set_collapsed chamado
    # pelo código); o argumento é o novo estado "collapsed".
    userToggled = pyqtSignal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._collapsed = False
        self._base_title = _QtGroupBox.title(self)
        self._restore_visible = []
        self._restore_min_h = 0
        self._restore_max_h = 16777215
        self._refresh_title()

    # ---- título (o texto "limpo" continua acessível via title()) ----
    def setTitle(self, title):
        self._base_title = str(title or "")
        self._refresh_title()

    def title(self):
        return self._base_title

    def _refresh_title(self):
        if not self._base_title:
            _QtGroupBox.setTitle(self, "")
            return
        arrow = self._ARROW_CLOSED if self._collapsed else self._ARROW_OPEN
        _QtGroupBox.setTitle(self, arrow + self._base_title)

    # ---- colapso ----
    def is_collapsed(self):
        return self._collapsed

    def _direct_child_widgets(self):
        return [c for c in self.children() if isinstance(c, QWidget) and not c.isWindow()]

    def _collapsed_height(self):
        return max(28, self.fontMetrics().height() + 14)

    def set_collapsed(self, collapsed):
        collapsed = bool(collapsed) and bool(self._base_title)
        if collapsed == self._collapsed:
            return
        if collapsed:
            children = self._direct_child_widgets()
            # só conta como "escondido de propósito" quem recebeu hide()/setVisible(False) explícito
            self._restore_visible = [
                w for w in children
                if not (w.isHidden() and w.testAttribute(Qt.WA_WState_ExplicitShowHide))
            ]
            self._restore_min_h = self.minimumHeight()
            self._restore_max_h = self.maximumHeight()
            for w in children:
                w.setVisible(False)
            self._collapsed = True
            self.setFixedHeight(self._collapsed_height())
        else:
            self._collapsed = False
            self.setMinimumHeight(self._restore_min_h)
            self.setMaximumHeight(self._restore_max_h)
            for w in self._restore_visible:
                w.setVisible(True)
            self._restore_visible = []
        self._refresh_title()
        self.updateGeometry()

    def mousePressEvent(self, event):
        if (event.button() == Qt.LeftButton and self._base_title
                and event.pos().y() <= self._collapsed_height()):
            self.set_collapsed(not self._collapsed)
            event.accept()
            self.userToggled.emit(self._collapsed)
            return
        super().mousePressEvent(event)


class LogConsole(QTextEdit):
    """Console somente-leitura com auto-scroll, carimbo de hora opcional e destaque de erros/avisos.

    Limita o número de blocos para que execuções longas de MD (milhares de linhas) não travem a GUI."""

    _ERR = re.compile(r"\b(error|erro|fatal|failed|falha|traceback|exception)\b", re.I)
    _WARN = re.compile(r"\b(warning|aviso|attention|atenção)\b", re.I)

    def __init__(self, parent=None, max_blocks=20000):
        super().__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(max_blocks)
        self.setLineWrapMode(QTextEdit.NoWrap)
        self.setStyleSheet(
            f"background:{PALETTE['console_bg']};color:#D6E2EE;font-family:'DejaVu Sans Mono',monospace;"
            f"font-size:9pt;border:1px solid {PALETTE['border']};border-radius:4px;"
        )

    def log(self, message, stamp=False):
        if message is None:
            return
        for line in str(message).splitlines() or [""]:
            line = line.rstrip()
            if stamp and line:
                line = f"[{datetime.now().strftime('%H:%M:%S')}] {line}"
            esc = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if self._ERR.search(line):
                esc = f"<span style='color:{PALETTE['danger_soft']};'>{esc}</span>"
            elif self._WARN.search(line):
                esc = f"<span style='color:{PALETTE['warn']};'>{esc}</span>"
            elif line.startswith("#"):
                esc = f"<span style='color:{PALETTE['accent']};font-weight:bold;'>{esc}</span>"
            else:
                esc = f"<span>{esc}</span>" if esc else "&nbsp;"   # com tag, o Qt trata como HTML (senão &gt; apareceria literal)
            self.append(esc)
        self.moveCursor(QTextCursor.End)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


def make_separator():
    """Linha fina em relevo (sunken), igual à do CODRUG: dá ideia de profundidade em vez de uma faixa chapada."""
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    line.setStyleSheet(f"color:{PALETTE['border']};")
    return line


def make_title(text="", size=14):
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(f"font-size:{size}pt;font-weight:bold;color:{PALETTE['text']};")
    return lbl


def make_progress(fmt="%p%"):
    bar = QProgressBar()
    bar.setFormat(fmt)
    bar.setMinimum(0)
    bar.setMaximum(100)
    bar.setValue(0)
    return bar


def make_kv_label(text, muted=True):
    lbl = QLabel(text)
    if muted:
        lbl.setStyleSheet(f"color:{PALETTE['muted']};font-size:9pt;")
    else:
        lbl.setStyleSheet(f"font-weight:bold;font-size:9pt;color:{PALETTE['text']};")
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lbl
