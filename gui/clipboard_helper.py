import tkinter as tk
import customtkinter as ctk

def paste_to_widget(target):
    try:
        text = target.clipboard_get()
    except Exception:
        return

    # Если это CTkEntry
    if isinstance(target, ctk.CTkEntry):
        target.insert("insert", text)
    # Если это CTkTextbox
    elif isinstance(target, ctk.CTkTextbox):
        target.insert("insert", text)
    # Обычный tk.Entry
    elif isinstance(target, tk.Entry):
        target.insert(tk.INSERT, text)
    # Обычный tk.Text
    elif isinstance(target, tk.Text):
        target.insert(tk.INSERT, text)


def copy_from_widget(target):
    try:
        if isinstance(target, ctk.CTkEntry):
            inner = getattr(target, "_entry", target)
            selected = inner.selection_get()
        elif isinstance(target, ctk.CTkTextbox):
            selected = target.get("sel.first", "sel.last")
        elif isinstance(target, tk.Entry):
            selected = target.selection_get()
        elif isinstance(target, tk.Text):
            selected = target.get(tk.SEL_FIRST, tk.SEL_LAST)
        else:
            return

        target.clipboard_clear()
        target.clipboard_append(selected)
    except Exception:
        pass


def cut_from_widget(target):
    copy_from_widget(target)
    try:
        if isinstance(target, ctk.CTkEntry):
            inner = getattr(target, "_entry", target)
            inner.delete(tk.SEL_FIRST, tk.SEL_LAST)
        elif isinstance(target, ctk.CTkTextbox):
            target.delete("sel.first", "sel.last")
        elif isinstance(target, tk.Entry):
            target.delete(tk.SEL_FIRST, tk.SEL_LAST)
        elif isinstance(target, tk.Text):
            target.delete(tk.SEL_FIRST, tk.SEL_LAST)
    except Exception:
        pass


def select_all_widget(target):
    try:
        if isinstance(target, ctk.CTkEntry):
            inner = getattr(target, "_entry", target)
            inner.select_range(0, tk.END)
            inner.icursor(tk.END)
        elif isinstance(target, ctk.CTkTextbox):
            target.tag_add("sel", "1.0", "end")
        elif isinstance(target, tk.Entry):
            target.select_range(0, tk.END)
            target.icursor(tk.END)
        elif isinstance(target, tk.Text):
            target.tag_add(tk.SEL, "1.0", tk.END)
    except Exception:
        pass


def show_context_menu(event, target):
    menu = tk.Menu(target, tearoff=0, bg="#2b2b2b", fg="#ffffff", activebackground="#1f538d", activeforeground="#ffffff")
    menu.add_command(label="📋 Вставить", command=lambda: paste_to_widget(target))
    menu.add_command(label="📄 Копировать", command=lambda: copy_from_widget(target))
    menu.add_command(label="✂️ Вырезать", command=lambda: cut_from_widget(target))
    menu.add_separator()
    menu.add_command(label="🔘 Выделить всё", command=lambda: select_all_widget(target))

    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def make_pasteable(widget):
    """
    Добавляет поддержку горячих клавиш (включая русскую раскладку)
    и контекстное меню по правому клику мыши.
    """
    targets = [widget]
    # Если внутри CustomTkinter есть встроенный tkinter-виджет
    inner = getattr(widget, "_entry", None) or getattr(widget, "_textbox", None)
    if inner is not None:
        targets.append(inner)

    def _on_key(event):
        # На Windows event.state & 4 означает зажатый Ctrl
        ctrl_pressed = bool(event.state & 4) or bool(event.state & 0x20000)
        if not ctrl_pressed:
            return

        # Keycode 86 = V / М (русская раскладка)
        if event.keycode == 86 or event.keysym.lower() in ("v", "cyrillic_em", "m"):
            paste_to_widget(widget)
            return "break"
        # Keycode 67 = C / С
        elif event.keycode == 67 or event.keysym.lower() in ("c", "cyrillic_es", "s"):
            copy_from_widget(widget)
            return "break"
        # Keycode 88 = X / Ч
        elif event.keycode == 88 or event.keysym.lower() in ("x", "cyrillic_che"):
            cut_from_widget(widget)
            return "break"
        # Keycode 65 = A / Ф
        elif event.keycode == 65 or event.keysym.lower() in ("a", "cyrillic_ef"):
            select_all_widget(widget)
            return "break"

    def _on_right_click(event):
        show_context_menu(event, widget)
        return "break"

    for t in targets:
        t.bind("<KeyPress>", _on_key, add="+")
        t.bind("<Button-3>", _on_right_click, add="+")
