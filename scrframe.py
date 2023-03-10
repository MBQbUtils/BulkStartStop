import tkinter as tk
import tkinter.ttk as ttk


class ScrollableFrame(ttk.Frame):
    """
    There is no way to scroll <tkinter.Frame> so we are
    going to create a canvas and place the frame there.
    Scrolling the canvas will give the illution of scrolling
    the frame
    Partly taken from:
        https://blog.tecladocode.com/tkinter-scrollable-frames/
        https://stackoverflow.com/a/17457843/11106801

    master_frame---------------------------------------------------------
    | dummy_canvas-----------------------------------------  y_scroll--  |
    | | self---------------------------------------------  | |         | |
    | | |                                                | | |         | |
    | | |                                                | | |         | |
    | | |                                                | | |         | |
    | |  ------------------------------------------------  | |         | |
    |  ----------------------------------------------------  |         | |
    |                                                        |         | |
    | x_scroll---------------------------------------------  |         | |
    | |                                                    | |         | |
    |  ----------------------------------------------------   ---------  |
     --------------------------------------------------------------------
    """

    def __init__(self, master=None, scroll_speed=2,
                 hscroll=False, vscroll=True, **kwargs):
        assert isinstance(scroll_speed, int), "`scroll_speed` must be an int"
        self.scroll_speed = scroll_speed

        self.master_frame = ttk.Frame(master)
        self.dummy_canvas = tk.Canvas(self.master_frame, **kwargs)
        super().__init__(self.dummy_canvas)

        # Create the 2 scrollbars
        if vscroll:
            self.v_scrollbar = ttk.Scrollbar(self.master_frame,
                                            orient="vertical",
                                            command=self.dummy_canvas.yview)
            self.v_scrollbar.pack(side="right", fill="y")
            self.dummy_canvas.configure(yscrollcommand=self.v_scrollbar.set)
        if hscroll:
            self.h_scrollbar = ttk.Scrollbar(self.master_frame,
                                            orient="horizontal",
                                            command=self.dummy_canvas.xview)
            self.h_scrollbar.pack(side="bottom", fill="x")
            self.dummy_canvas.configure(xscrollcommand=self.h_scrollbar.set)

        # Bind to the mousewheel scrolling
        self.dummy_canvas.bind_all("<MouseWheel>", self.scrolling_windows,
                                   add=True)
        self.dummy_canvas.bind_all("<Button-4>", self.scrolling_linux, add=True)
        self.dummy_canvas.bind_all("<Button-5>", self.scrolling_linux, add=True)
        self.bind("<Configure>", self.scrollbar_scrolling, add=True)

        # Place `self` inside `dummy_canvas`
        self.dummy_canvas.create_window((0, 0), window=self, anchor="nw")
        # Place `dummy_canvas` inside `master_frame`
        self.dummy_canvas.pack(side="top", expand=True, fill="both")

        self.pack = self.master_frame.pack
        self.grid = self.master_frame.grid
        self.place = self.master_frame.place
        self.pack_forget = self.master_frame.pack_forget
        self.grid_forget = self.master_frame.grid_forget
        self.place_forget = self.master_frame.place_forget

    def scrolling_windows(self, event):
        assert event.delta != 0, "On Windows, `event.delta` should never be 0"
        y_steps = int(-event.delta / abs(event.delta) * self.scroll_speed)
        self.dummy_canvas.yview_scroll(y_steps, "units")

    def scrolling_linux(self, event):
        y_steps = self.scroll_speed
        if event.num == 4:
            y_steps *= -1
        self.dummy_canvas.yview_scroll(y_steps, "units")

    def scrollbar_scrolling(self, event):
        region = list(self.dummy_canvas.bbox("all"))
        region[2] = max(self.dummy_canvas.winfo_width(), region[2])
        region[3] = max(self.dummy_canvas.winfo_height(), region[3])
        self.dummy_canvas.configure(scrollregion=region)

    def resize(self, fit=None, height=None, width=None):
        if fit == tk.FIT_WIDTH:
            super().update()
            self.dummy_canvas.config(width=super().winfo_width())
        if fit == tk.FIT_HEIGHT:
            super().update()
            self.dummy_canvas.config(height=super().winfo_height())
        if height is not None:
            self.dummy_canvas.config(height=height)
        if width is not None:
            self.dummy_canvas.config(width=width)

    fit = resize
