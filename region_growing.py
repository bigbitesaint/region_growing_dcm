import pydicom
import png
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox, filedialog
from enum import Enum
import numpy as np
import copy
import math
import os
import winreg
from collections import deque


scale_factor = 4

class DcmRawImage:
    class Mode(Enum):
        PLAIN = 1
        REGION = 2

    def __init__(self, dcm):
        #print(dcm.NumberOfFrames)
        self.img = dcm.pixel_array
        self.region_growing = copy.copy(self.img)
        self.curr_img_index = 0

        print(dcm.pixel_array.shape)

    def slices(self):
        return self.img.shape[0]

    def size(self):
        return self.img.shape

    def curr_index(self):
        return self.curr_img_index

    def set_index(self, idx):
        self.curr_img_index = idx
        

    def get(self, idx=-1, mode=Mode.PLAIN):
        if idx < 0:
            idx = self.curr_img_index

        if mode == DcmRawImage.Mode.PLAIN:
            return self.img[idx]
        elif mode == DcmRawImage.Mode.REGION:
            if self.region_growing is None:
                raise Exception('Region growing has not yet be done.')
            return self.region_growing[idx]
        else:
            raise Exception('Unknown mode:', mode)

    def toggle(self, x, y, idx=-1, mode=Mode.PLAIN):
        if idx < 0:
            idx = self.curr_img_index

        src = None
        if mode == DcmRawImage.Mode.PLAIN:
            src = self.img
        elif mode == DcmRawImage.Mode.REGION:
            if self.region_growing is None:
                raise Exception('Region growing has not yet be done.')
            src = self.region_growing
        else:
            raise Exception('Unknown mode:', mode)        
        
        src[idx][y][x] = 0 if src[idx][y][x] > 0 else 65535
        slide_show(0)

    def do_rg(self, seed, method='INTENSITY', delta=100, range_max=65535):
        size = self.img.shape
        print('Image size:', size)

        self.region_growing = np.zeros( size, dtype=np.uint16)
        visited = np.zeros( size )

        queue = deque([])
        queue.append(seed)

        z, x, y = seed
        total_sum = int(self.img[ seed[0] ][ seed[1] ][ seed[2] ])
        total_count = 1

        while len(queue) > 0:
            item = queue.popleft()


            for dir in [    [1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1] ]:
                next_pos = [ item[0] + dir[0] , item[1] + dir[1], item[2] + dir[2] ]
                if      next_pos[0] >=0 and next_pos[0] < size[0] and\
                        next_pos[1] >=0 and next_pos[1] < size[1] and\
                        next_pos[2] >=0 and next_pos[2] < size[2] and\
                        visited[ next_pos[0] ][ next_pos[1] ][ next_pos[2] ] == 0:
                    visited[ next_pos[0] ][ next_pos[1] ][ next_pos[2] ] = 1

                    diff = int(total_sum / total_count) - int(self.img[ next_pos[0] ][ next_pos[1] ][ next_pos[2] ])

                    if diff < delta:
                        #print('Pos:',next_pos, 'Diff:', diff)
                        queue.append( [next_pos[0], next_pos[1], next_pos[2] ] )
                        total_sum += self.img[ next_pos[0] ][ next_pos[1] ][ next_pos[2] ]
                        total_count += 1
                        self.region_growing[ next_pos[0] ][ next_pos[1] ][ next_pos[2] ] = range_max

        slide_show(0)



def mouse_wheel(event):
    if event.delta > 0:
        slide_show(1)
    else:
        slide_show(-1)

def slide_show(step):
    global img_panel
    global region_growing_panel
    global dcm

    # update index
    next_idx = ( dcm.curr_index() + step + dcm.slices() ) % dcm.slices()


    dcm.set_index(  next_idx  )
    

    # update text
    img_index.configure(text=str(dcm.curr_index() + 1 ) + '/' + str(dcm.slices() ) )
    img_index.pack()

    # update image
    img_slice = dcm.get()
    # normalize view
    img_slice = np.divide( img_slice, np.amax(img_slice) / 256 ).astype(np.uint16)
    img_slice = np.kron(img_slice, np.ones( (scale_factor,scale_factor) ))
    img = Image.fromarray(img_slice)
    tkimage = ImageTk.PhotoImage(img)
    img_panel.configure(image=tkimage )
    img_panel.image = tkimage
    img_panel.pack()

    # update region growing image
    img_slice = dcm.get(mode=DcmRawImage.Mode.REGION)
    # normalize view
    img_slice = np.divide( img_slice, np.amax(img_slice) / 256 ).astype(np.uint16)    
    img_slice = np.kron(img_slice, np.ones( (scale_factor,scale_factor) ))
    img = Image.fromarray(img_slice)
    tkimage = ImageTk.PhotoImage(img)
    region_growing_panel.configure(image=tkimage )
    region_growing_panel.image = tkimage
    region_growing_panel.pack()    





def hover_event(event):
    global img_coor
    global orig_value_label
    global rg_value_label
    global dcm
    src = event.widget

    x, y = event.x, event.y
    x = int(x / scale_factor)
    y = int(y / scale_factor)


    img_coor['text'] = '(' + str(x) + ',' + str(y) + ')'
    try:
        orig_value_label['text'] = str(dcm.get(mode=DcmRawImage.Mode.PLAIN)[y][x])
        rg_value_label['text']   = str(dcm.get(mode=DcmRawImage.Mode.REGION)[y][x])        
        # FIXME: strange reversed index
        #orig_value_label['text'] = str(dcm.get(mode=DcmRawImage.Mode.PLAIN)[x][y])
        #rg_value_label['text']   = str(dcm.get(mode=DcmRawImage.Mode.REGION)[x][y])
    except IndexError:
        pass


    #print(event.x, event.y)



def click_event(event):
    global str_seed_x
    global str_seed_y
    global str_seed_z
    global dcm
    

    x, y = event.x, event.y
    x = int(x / scale_factor)
    y = int(y / scale_factor)

    str_seed_x.set(str(x))
    str_seed_y.set(str(y))
    str_seed_z.set(str(dcm.curr_index()+1))


def toggle_event(event):
    global dcm
    
    

    x, y = event.x, event.y
    x = int(x / scale_factor)
    y = int(y / scale_factor)

    dcm.toggle(x, y, mode=DcmRawImage.Mode.REGION)

def scroll_event(*args):
    global scrollbar
    if dcm is not None:
        scrollbar.set(args[1], args[1])
        curr_idx = dcm.curr_index()
        target_idx = int( float(args[1]) * dcm.slices()) - 1
        if target_idx < 0:
            return
        
        slide_show( target_idx - curr_idx )
        

def open_file():
    global dcm

    dirpath = read_reg('FileOpenHistory')
    dirpath = './' if dirpath is None else os.path.dirname(dirpath)
    print('InitialDir:' + dirpath)
    filename = filedialog.askopenfilename(initialdir=dirpath, title='Select File', filetypes = (("DICOM files","*.dcm"),("all files","*.*")))
    try:
        if len(filename) > 0:
            write_reg('FileOpenHistory', filename)
            dcm = DcmRawImage(pydicom.dcmread(filename))
            slide_show(0)
    except IOError:
        tk.messagebox.showerror(title='Error', message='File open error!')
    
    

def save_file():
    global dcm
    global rg_seed_x
    global rg_seed_y
    global rg_seed_z
    global rg_delta

    dirpath = read_reg('FileOpenHistory')
    dirpath = './' if dirpath is None else os.path.dirname(dirpath)
    print('InitialDir:', dirpath)
    dirname = filedialog.askdirectory(initialdir=dirpath, title='Select File')
    try:
        if len(dirname) > 0:
            writer = png.Writer(width=dcm.size()[2], height=dcm.size()[1], bitdepth=16, greyscale=True)
            for i in range(dcm.slices()):
                slice = dcm.get(idx=i, mode=DcmRawImage.Mode.REGION)
                with open(os.path.join( dirname, '{:03d}.PNG'.format(i)), 'wb') as f:
                    writer.write(f, slice.tolist())
            
            with open(os.path.join( dirname, 'param.txt'), 'w') as f:
                print('Slice:{}, X:{}, Y:{}, Delta:{}'.format(rg_seed_z.get(), rg_seed_x.get(), rg_seed_y.get(), rg_delta.get()), file=f)
                tk.messagebox.showinfo(title='Success', message='File saved successfully.')
    except IOError:
        tk.messagebox.showerror(title='Error', message='File save error!')
    
    

def run_region_growing():
    global rg_seed_x
    global rg_seed_y
    global rg_seed_z
    global rg_delta
    global dcm

    seed_x = int(rg_seed_x.get())
    seed_y = int(rg_seed_y.get())
    seed_z = int(rg_seed_z.get()) - 1
    delta  = int(rg_delta.get())

    if seed_x < 0 or seed_x >= dcm.size()[1]:
        tk.messagebox.showerror(title='Error', message='Invalid seed X:' + rg_seed_x.get() )
    elif seed_y < 0 or seed_y >= dcm.size()[2]:
        tk.messagebox.showerror(title='Error', message='Invalid seed Y:' + rg_seed_y.get() )
    elif seed_z < 0 or seed_z >= dcm.size()[0]:
        tk.messagebox.showerror(title='Error', message='Invalid Slice:' + rg_seed_z.get() )
    else:
        dcm.do_rg( seed=(seed_z, seed_y, seed_x), delta=delta)


REG_PATH = "Region Growing"
def write_reg(name, value):
    try:
        winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH)
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        winreg.CloseKey(key)
        return True
    except WindowsError:
        return False

def read_reg(name):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        print(winreg.QueryInfoKey(key))
        val, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return val
    except WindowsError as e:
        print(e)
        return None


if __name__ == '__main__':
    #dcm = DcmRawImage(pydicom.dcmread('SubtractionResultVOI.dcm'))
    dcm = None
    
    
    root = tk.Tk()
    root.title('RegionFrowing')
    root.geometry( '600x600' )
    tk.Button(root, text='Open file', command=open_file).pack()

    frame_rg = tk.Frame(root, relief=tk.RAISED, borderwidth=1)
    tk.Label(frame_rg, text='Slice:').grid(row=0, column=0)
    str_seed_z = tk.StringVar()
    rg_seed_z = tk.Entry(frame_rg, textvariable=str_seed_z)
    rg_seed_z.grid(row=0, column=1)

    tk.Label(frame_rg, text='X').grid(row=1, column=0)
    str_seed_x = tk.StringVar()
    rg_seed_x = tk.Entry(frame_rg, textvariable=str_seed_x)
    rg_seed_x.grid(row=1, column=1)

    tk.Label(frame_rg, text='Y').grid(row=2, column=0)
    str_seed_y = tk.StringVar()
    rg_seed_y = tk.Entry(frame_rg, textvariable=str_seed_y)
    rg_seed_y.grid(row=2, column=1)

    tk.Label(frame_rg, text='Delta').grid(row=3, column=0)
    rg_delta = tk.Entry(frame_rg)
    rg_delta.grid(row=3, column=1)

    tk.Button(frame_rg, text='Region Growing', command=run_region_growing ).grid(row=4, column=0, columnspan=2)
    frame_rg.pack(expand=True)


    # create index count
    img_index = tk.Label(root)
    img_index.pack()

    # create coordinate
    img_coor = tk.Label(root)
    img_coor.pack()

    # scroll bar
    scrollbar = tk.Scrollbar(root, orient=tk.HORIZONTAL, command=scroll_event)
    scrollbar.pack(fill=tk.X)
    

    # create up/down button
    tk.Button(root, text='<', command=lambda: slide_show(-1)).pack(side=tk.LEFT)
    tk.Button(root, text='>', command=lambda: slide_show(1)).pack(side=tk.RIGHT)

    # create information labels
    frame_top = tk.Frame(root)
    frame_top.pack(fill=tk.X)

    orig_value_label = tk.Label(frame_top, text='(0)', fg='red')
    orig_value_label.pack(side=tk.LEFT)

    rg_value_label = tk.Label(frame_top, text='(0)', fg='red')
    rg_value_label.pack(side=tk.RIGHT, expand=True)


    # create image frame
    frame_image = tk.Frame(root)
    frame_image.pack(fill=tk.X)

    # create image
    img_panel = tk.Label(frame_image)
    img_panel.pack(side=tk.LEFT)

    # create region growing image
    region_growing_panel = tk.Label(frame_image)
    region_growing_panel.pack(side=tk.RIGHT, expand=True)


    # bottom frame
    frame_bottom = tk.Frame(root)
    tk.Button(frame_bottom, text='Save File', command=save_file).pack(fill=tk.X, expand=True)
    frame_bottom.pack(fill=tk.X, expand=True)

    # bind event
    root.bind('<MouseWheel>', mouse_wheel)
    img_panel.bind('<Motion>', hover_event)
    img_panel.bind('<Button-1>', click_event)
    
    region_growing_panel.bind('<Motion>', hover_event)
    region_growing_panel.bind('<Button-1>', click_event)
    region_growing_panel.bind('<Control-Button-1>', toggle_event)

    
    #slide_show(0)

    root.mainloop()


    
    


