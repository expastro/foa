import ROOT
import numpy as np
import time 

import Tkinter as tk
from tkFileDialog import askopenfilename
import tkMessageBox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.figure import Figure 
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

import datetime

experimental = True

if experimental:
	try:
		from root_numpy import tree2array
	except:
		experimental = False
		print "root_numpy could not be loaded! Using fallback method. Be aware\
, this is slower when activating more than 1 channel!"


def is_number(instr):
	try:
		out =float(instr)
		return True
	except:
		return False

class LoadRoot():
	"""Load data from ROOT. This is not very efficient at the moment as it
	runs through all events for each channel. But its still faster the running
	all events in python loop.
	"""
	def __init__(self,filename):
		ROOT.gROOT.SetBatch()
		self.filename = filename
		self.load()
		self.temp = 0
		
	def load(self):
		self.rfile = ROOT.TFile(self.filename)
	
	def check_tree_number(self):
		self.keys = [key.GetName() for key in ROOT.gDirectory.GetListOfKeys()]
		tree_nbr = self.keys.count("h509")
		return self.keys, tree_nbr
	
	def get_data(self, leafname, xmin, xmax, bins, ch):
		x_lst = []
		y_lst = []
		hist = ROOT.gROOT.FindObject("h509")
		hist.Draw('{}>>test{}({},{},{})'.format(leafname, self.temp, bins, xmin, xmax), "ch=={}".format(ch))
		histo = ROOT.gROOT.FindObject("test{}".format(self.temp))
		self.temp += 1
		
		## this method is new but don't seem to work with older root versions
		# ~ for i, bin_ in enumerate(histo):
			# ~ pos = histo.GetBinCenter(i)
			# ~ x_lst.append(pos)
			# ~ x_lst.append(pos + histo.GetBinWidth(i))
			
			# ~ y_lst.append(bin_)
			# ~ y_lst.append(bin_)
		
		maxb = histo.GetNbinsX() + 1
		for i in range(0, maxb):
			pos = histo.GetBinCenter(i)
			x_lst.append(pos)
			x_lst.append(pos + histo.GetBinWidth(i))
			
			y_lst.append(histo.GetBinContent(i))
			y_lst.append(histo.GetBinContent(i))
		
		
		return [np.array(x_lst), np.array(y_lst), datetime.datetime.now()]
	
	def get_data_all(self, detector_lst):
		all_out_lst = []
		for det in detector_lst:
			all_out_lst.append(self.get_data(det["leaf"], det["min"], det["max"], det["bin"], det["ch"]))
		
		return all_out_lst

	def get_data_ex(self):
		intree = self.rfile.Get('h509')
		self.tree_array = tree2array(intree, branches = ["ch", "longgate", "t"])



	def get_data_all_ex(self, detector_lst):
		self.get_data_ex()
		
		all_out_lst = []

		
		for det in detector_lst:
			x_lst = []
			y_lst = []
			tt = np.histogram(self.tree_array[self.tree_array['ch'] == int(det["ch"])][det["leaf"]], bins = int(det["bin"]), range=(det["min"],det["max"]))
			
			bin_width = tt[1][1] - tt[1][0]
			
			for i in range(0, len(tt[0])):
				pos = tt[1][i]
				x_lst.append(pos)
				x_lst.append(pos + bin_width)
				
				y_pos = tt[0][i]
				y_lst.append(y_pos)
				y_lst.append(y_pos)
			
			all_out_lst.append([np.array(x_lst), np.array(y_lst), datetime.datetime.now()])
		
		return all_out_lst

	def close(self):
		self.rfile.close()

class Gui():
	"""Creates the grahical user interface"""
	def __init__(self):
		"""Creates main window."""
		### init variables
		## default update interval
		self.update_interval = 5
		## load a file for the rest of the program to work
		self.file_loaded = False
		self.ref_time = datetime.datetime.now()
		## init the counts in window
		self.ciw = {}
		## number of channels on DAQ board
		self.ports = 8
		for j in range(self.ports):
			self.ciw[j] = 0
		self.ciw_ref = {}
		for j in range(self.ports):
			self.ciw_ref[j] = 0
		## draw the canvas on init
		self.draw_once = True
		## nbr detectors that are pluged in 
		self.detector_lst = []
		## dummy for gui
		self.detector_all_lst = []
		
		## default vals
		self.min_default = 0
		self.max_default = 70000
		self.max_default_t = 1.e12
		self.bin_default = 1000
		self.bin_default_t = 10000
		
		for j in range(self.ports):
			self.detector_all_lst.append({"ch" : j, "min" : self.min_default, "max": self.max_default, \
			"bin": self.bin_default, "leaf" : "longgate", "on":False, "yscale" : "lin", \
			"name":"Channel {}".format(j)})
		## tk and matplotlib variables
		self.data_arr = []
		self.ln = []
		self.lim_dic = {}
		self.colors = ['midnightblue', 'darkorange', 'darkred','darkgreen', 'blueviolet', 'goldenrod', 'darkgray']
		self.int_vars = []
		self.min_vars = []
		self.max_vars = []
		self.bin_vars = []
		self.name_vars = []
		self.choice_vars = []
		self.choices = ["linear", "log"]
		self.leaf = ["longgate", "t"]
		self.leaf_vars = []
		self.det_count = 0
		self.update_cycle = 0
		self.skip_to_load = False
		
		## debugging var
		self.temp2 = 1
		self.data_sim = 1.01
		
		
		### Create main window

		self.root = tk.Tk()
		self.root.title("VdG Viewer")
		self.root.geometry("800x600")
		
		### Create a menu bar
		self.menubar = tk.Menu(self.root)
		self.root.config(menu = self.menubar)
		self.menu_bar()
		
		## more tk variables that needed the root window
		self.cycle_var = tk.StringVar()
		self.update_var = tk.StringVar()
		self.refresh_var = tk.StringVar()
		self.load_var = tk.StringVar()
		self.auto_scale = tk.IntVar()
		self.safty_var = tk.IntVar()
		self.safty_var.set(1)
		self.stop_refresh = tk.IntVar()
		self.stop_refresh.set(1)

		## hard shutdown when pressing the x
		self.root.protocol("WM_DELETE_WINDOW", lambda: self.end())
		
		## tk mainloop
		self.root.mainloop()
		
	
	def plot(self):
		""" Function to create the main matplotlib plot """
		
		## delete the default matplotlib home button
		class CustomToolbar(NavigationToolbar2TkAgg):
			toolitems = filter(lambda x: x[0] != "Home", NavigationToolbar2TkAgg.toolitems)
		
		
		## number of plots depending on used channels
		if len(self.detector_lst) <=3 :
			self.f, self.ax = plt.subplots(len(self.detector_lst))
		elif len(self.detector_lst) <=4:
			self.f, self.ax = plt.subplots(2, 2)
		elif len(self.detector_lst) <=6:
			self.f, self.ax = plt.subplots(3, 2)
		else:
			self.f, self.ax = plt.subplots(3, 3)
		
		## flatten the nested np.array so one loop is enough
		## check axes type to np.array so it works with just one channel
		if type(self.ax) == np.ndarray:
			self.ax = self.ax.flatten()
		else:
			self.ax = np.array([self.ax])
		
		
		## load the data for the first time
		self.root_data()

		self.canvas = FigureCanvasTkAgg(self.f, master=self.show_plot)
		self.canvas.get_tk_widget().pack(side=tk.TOP,expand=tk.YES,fill=tk.BOTH)

		self.toolbar_frame = tk.Frame(self.show_plot) 
		self.toolbar_frame.pack(side=tk.LEFT)
		
		# ~ self.toolbar = NavigationToolbar2TkAgg( self.canvas, self.toolbar_frame )
		self.toolbar = CustomToolbar(self.canvas,self.toolbar_frame)
		self.toolbar.update()
		# ~ self.ln, = self.ax.plot(self.xarr, self.yarr, animated=True)
		
		## create plot for every channel in list
		for i in range(0, len(self.detector_lst)):
			self.ln.append((self.ax[i].plot(self.data_arr[i][0], self.data_arr[i][1], lw = 0.9, color = self.colors[i], animated=True))[0])
			self.ax[i].grid(linestyle = "-", linewidth = "0.5", color = "grey", alpha = 0.5)
			self.ax[i].set_yscale(self.detector_lst[i]["yscale"])
		if self.draw_once == True:
			self.canvas.draw()
			self.draw_once = False
		
		self.f.tight_layout(pad = 0.8)
		
		self.ani = FuncAnimation(self.f, self.update, interval = 300, blit=True)
		




	def update(self,frame):
		"""This is used to update the plot every time FuncAnimation calls it"""
		self.root_data(time = True)
		for i in range(0, len(self.detector_lst)):
			## reload the date 
			
			
			## read the current axes limits
			self.lim_dic[i] = [self.ax[i].get_xlim(), self.ax[i].get_ylim()]

			## read the counts in window 
			self.counts_in_window(i)
			## set the axis limits from list. this keeps the current zoom
			## level
			self.ax[i].set_xlim(self.lim_dic[i][0])
			self.ax[i].set_ylim(self.lim_dic[i][1])
			
			## set legend label and title
			self.ln[i].set_label(str(self.ciw[i]))			
			leg = self.ax[i].legend(loc = "upper right", title = self.detector_lst[i]["name"])
			
			## set data
			self.ln[i].set_data(self.data_arr[i][0], self.data_arr[i][1] )
			
			## if a number of counts in window has changed, redraw the canvas
			if not self.ciw[i] == self.ciw_ref[i]:
				## this is needed to update the legend properly
				self.ani._blit_cache.clear()
				self.canvas.draw()
				self.ciw_ref[i] = self.ciw[i]
		return self.ln

	def auto_scale_axes(self):
		"""Sets limits so all data is displayed"""
		for i in range(0, len(self.detector_lst)):
			max_val_x = np.max(self.data_arr[i][0])
			max_val_y = np.max(self.data_arr[i][1])
			self.ax[i].set_xlim([-1 * max_val_x * 0.05, max_val_x * 1.05])
			self.ax[i].set_ylim([-1 * max_val_y * 0.05, max_val_y* 1.05])
		self.canvas.draw()
	

	def call_root(self, time):
		""" Loads the ROOT data"""
		root_instance = LoadRoot(self.filename)
		data_arr_bak = self.data_arr 
		self.data_arr = []
		
		try:
			if experimental:
				self.data_arr = root_instance.get_data_all_ex(self.detector_lst)
			else:
				self.data_arr = root_instance.get_data_all(self.detector_lst)
		except:
			print "Error while loading data. Retry in {}s".format(self.update_interval)
			if len(self.data_arr) > 0:
				self.data_arr = data_arr_bak
				self.ref_time = datetime.datetime.now()
			else:
				self.data_arr = [[np.arange(100), np.zeros(100), datetime.datetime.now()]]
		# ~ for det in self.detector_lst:
			# ~ data = root_instance.get_data(det["leaf"], det["min"], det["max"], det["bin"], det["ch"])
			
			## this is for debugging to simulate data income
			# ~ print self.temp, np.max(data[1] * self.temp)
			# ~ self.data_arr.append([data[0], data[1] * self.data_sim, data[2]])
			
			# ~ self.data_arr.append(data)
		
		## debugging
		# ~ self.data_sim += 0.1
		
		## time: end of loading process
		self.ref_time = self.data_arr[-1][-1]
		


	def root_data(self, time = False):
		""" Stuff that gets done when new data is loaded """
		


		if ((datetime.datetime.now() - self.ref_time).total_seconds() > self.update_interval and self.stop_refresh.get() == 1) or time == False:
		## display the loading message. this has to be done with a return 
		## because the loading process blocks the main process and the 
		## message wouldn't be displayed 
			if self.skip_to_load:
				self.load_var.set("Loading Data...")
				self.skip_to_load = False
				return
			## time: start of loading process
			cycle_start = datetime.datetime.now()

			self.call_root(time = time)
			

			self.skip_to_load = True
			
			## time the loading took
			self.update_cycle = (self.ref_time - cycle_start).total_seconds()
			
			self.safty_update()

			## update the cycle label after each read process
			try:
				self.cycle_var.set("Update cycle: {:.2f}s".format(self.update_cycle))
				self.update_var.set("Refresh rate: {}s".format(self.update_interval))
			except:
				pass
			print "Updated data at {}".format(self.ref_time.strftime("%Y-%m-%d %H:%M:%S"))
			
			self.auto_scale_check()
			## next time skipt this if to display load message
			self.load_var.set("")
		else:
			pass



	def end(self):
		""" This kills the program """
		self.root.destroy()
		raise SystemExit()
	
	def counts_in_window(self, nbr):
		""" This sums the counts in the current x-range. For this to work 
		proberly only every 2nd element of the data arrays is used. This is
		necessary because to simulate a 'bin look' extra elements were added to 
		the array. See LoadRoot class.  """
		self.ciw[nbr] = np.sum(self.data_arr[nbr][1][0::2][(self.data_arr[nbr][0][0::2] > self.lim_dic[nbr][0][0]) & (self.data_arr[nbr][0][0::2] < self.lim_dic[nbr][0][1])])
	


	def menu_bar(self):
		"""Menu Bar"""
		## Create a pull-down menu, and add it to the menu bar
		pull_down_menu = tk.Menu(self.menubar, tearoff = 0)
		self.menubar.add_cascade(label = "File", menu = pull_down_menu)
		pull_down_menu.add_command(label = "Load...", command = self.load)
		pull_down_menu.add_command(label = "Exit", command = self.end)
		
		options_menu = tk.Menu(self.menubar, tearoff = 0)
		self.menubar.add_cascade(label = "Options", menu = options_menu)
		options_menu.add_command(label="Channel...", command = self.channel_window)
		options_menu.add_command(label="Viewer...", command = self.viewer_window)



	def load(self):
		""" Check if Channles are selected before a file is loaded"""
		if len(self.detector_lst) == 0:
			tkMessageBox.showwarning("No Channel selected", "Please activate at least one channel under Options > Channel before loading a file.")
		else:
			self.filename = askopenfilename()
			self.reload()

	def reload(self):
		""" Open a file. If this is not the first file, destroy all plot tk
		elements and empty lists"""
		if self.filename == "":
			return 
		else:
			try:
				for i in range(0, len(self.detector_lst)):
					self.ax[i].legend_.remove()
			except:
				pass
				
			destroy = []
			try:
				self.canvas.get_tk_widget().destroy()
				self.show_plot.destroy()
				self.fit_button.destroy()
				self.data_arr = []
				self.ciw = {}
				self.ln = []
				self.ax = []
				self.lim_dic = {}
				self.draw_once = True
				self.skip_to_load = False
			except:
				pass
			
			try:
				self.update_label.destroy()
				self.refresh_rate.destroy()
				self.auto_scale_ck.destroy()
				self.stop_refresh_ck.destroy()
			except:
				pass
			
			try:
				self.load_msg.destroy()
			except:
				pass
			
			## set window name to file path
			self.root.title("VdG Viewer" + " " + self.filename)
			self.file_loaded = True
			
			## make plot window and tk elements
			self.show_plot = tk.LabelFrame(self.root, text="Plot")
			self.show_plot.pack(side=tk.TOP,expand=tk.YES,fill=tk.BOTH, padx = 10)
			self.plot()

			self.fit_button = tk.Button(self.root, text='Reset View',\
			command = self.auto_scale_axes, width = 8)
			self.fit_button.pack(side=tk.LEFT,expand=tk.NO, padx = 5, pady = 5)
			
			self.cycle_var.set("Update cycle: {:.2f}s".format(self.update_cycle))
			self.update_label = tk.Label(self.root, textvariable=self.cycle_var)
			self.update_label.pack(side=tk.RIGHT, padx = 5, pady = 5)
			
			self.update_var.set("Refresh rate: {}s".format(self.update_interval))
			self.refresh_rate = tk.Label(self.root, textvariable=self.update_var)
			self.refresh_rate.pack(side=tk.RIGHT, padx = 5, pady = 5)
			
			# ~ self.load_var.set("")
			self.load_msg = tk.Label(self.root, textvariable=self.load_var)
			self.load_msg.pack(side=tk.RIGHT, padx = 5, pady = 5)

			self.auto_scale_ck = tk.Checkbutton(self.root, text="Auto rescale", variable=self.auto_scale)
			self.auto_scale_ck.pack(side = tk.LEFT, padx = 5, pady = 5)

			self.stop_refresh_ck = tk.Checkbutton(self.root, text="Refresh", variable=self.stop_refresh)
			self.stop_refresh_ck.pack(side = tk.LEFT, padx = 5, pady = 5)

	def auto_scale_check(self):
		""" Check if auto scale is checked"""
		if self.auto_scale.get() == 1:
			self.auto_scale_axes()
			print "Rescaled axes"
			

	def channel_window(self):
		""" Window for channel options"""
		self.channel_window = tk.Toplevel()
		self.channel_window.title("Choose Channel")
		
		self.chbuttons = []
		self.min_entry = []
		self.max_entry = []
		self.bin_entry = []
		self.choice_entry = []
		self.name_entry = []
		self.leaf_entry = []
		
		
		tk.Label(self.channel_window, text="Channel").grid(row = 0, column = 0)
		tk.Label(self.channel_window, text="Min").grid(row = 0, column = 1)
		tk.Label(self.channel_window, text="Max").grid(row = 0, column = 2)
		tk.Label(self.channel_window, text="Bin").grid(row = 0, column = 3)
		tk.Label(self.channel_window, text="y-Scale").grid(row = 0, column = 4)
		tk.Label(self.channel_window, text="Leaf").grid(row = 0, column = 5)
		tk.Label(self.channel_window, text="Name").grid(row = 0, column = 6)
		
		for ch in range(self.ports):
			self.int_vars.append(tk.IntVar())
			self.min_vars.append(tk.StringVar())
			self.max_vars.append(tk.StringVar())
			self.bin_vars.append(tk.StringVar())
			self.choice_vars.append(tk.StringVar())
			self.name_vars.append(tk.StringVar())
			self.leaf_vars.append(tk.StringVar())
			
			
			self.min_vars[ch].set(str(self.detector_all_lst[ch]["min"]))
			self.max_vars[ch].set(str(self.detector_all_lst[ch]["max"]))
			self.bin_vars[ch].set(str(self.detector_all_lst[ch]["bin"]))
			self.name_vars[ch].set(self.detector_all_lst[ch]["name"])
			self.choice_vars[ch].set(self.choices[0])
			self.leaf_vars[ch].set(self.leaf[0])
			
			self.chbuttons.append(tk.Checkbutton(self.channel_window, text=str(ch), variable=self.int_vars[ch]))
			self.chbuttons[ch].grid(row = ch +1 , column = 0, padx = (5,5), pady = (0,5), sticky = tk.W+tk.E)
			
			self.min_entry.append(tk.Entry(self.channel_window, textvariable = self.min_vars[ch], width = 10))
			self.min_entry[ch].grid(row = ch + 1, column = 1, padx = (5,5), pady = (0,5), sticky = tk.W)

			self.max_entry.append(tk.Entry(self.channel_window, textvariable = self.max_vars[ch], width = 10))
			self.max_entry[ch].grid(row = ch + 1, column = 2, padx = (5,5), pady = (0,5), sticky = tk.W)

			self.bin_entry.append(tk.Entry(self.channel_window, textvariable = self.bin_vars[ch], width = 10))
			self.bin_entry[ch].grid(row = ch + 1, column = 3, padx = (5,5), pady = (0,5), sticky = tk.W)
			
			self.choice_entry.append(tk.OptionMenu(self.channel_window, self.choice_vars[ch], *self.choices))
			self.choice_entry[ch].grid(row = ch + 1, column = 4, padx = (5,5), pady = (0,5), sticky = tk.W)
			
			self.leaf_entry.append(tk.OptionMenu(self.channel_window, self.leaf_vars[ch], *self.leaf, command = self.leaf_option_action ))
			self.leaf_entry[ch].grid(row = ch + 1, column = 5, padx = (5,5), pady = (0,5), sticky = tk.W)

			self.name_entry.append(tk.Entry(self.channel_window, textvariable = self.name_vars[ch], width = 10))
			self.name_entry[ch].grid(row = ch + 1, column = 6, padx = (5,5), pady = (0,5), sticky = tk.W)
		
		
		self.ch_button = tk.Button(self.channel_window, text='Accept',\
		command = self.channel_button, width = 8)
		self.ch_button.grid(row = 20, column = 0, padx = 10,\
		pady = 10)

	def leaf_option_action(self, dummy):
		for ch in range(self.ports):
			option = self.leaf_vars[ch].get()
			if option == "longgate":
				self.max_vars[ch].set(str(self.max_default))
				self.bin_vars[ch].set(str(self.bin_default))
			if option == "t":
				self.max_vars[ch].set(str(self.max_default_t))
				self.bin_vars[ch].set(str(self.bin_default_t))
	
	
	def viewer_window(self):
		"""Window for viewer options"""
		
		self.viewer_window = tk.Toplevel()
		self.viewer_window.title("Viewer Options")

		
		tk.Label(self.viewer_window, text="Refresh rate:").grid(row = 0, column = 0)
		self.refresh_var.set(str(self.update_interval))
		self.refresh_entry = (tk.Entry(self.viewer_window, textvariable = self.refresh_var, width = 5))
		self.refresh_entry.grid(row = 0, column = 1, padx = (5,0), pady = (0,5), sticky = tk.E)
		tk.Label(self.viewer_window, text="s").grid(row = 0, column = 2, sticky = tk.W)

		
		self.auto_scale_ck = tk.Checkbutton(self.viewer_window, text="Safty refresh", variable=self.safty_var)
		self.auto_scale_ck.grid(row = 1, column = 0, sticky = tk.W)
		
		self.ch_button2 = tk.Button(self.viewer_window, text='Accept',\
		command = self.channel_button2, width = 8)
		self.ch_button2.grid(row = 20, column = 0, padx = 10,\
		pady = 10)

	def channel_button(self):
		""" Channel Window Button action. Reads entry fields and checkboxes"""
		self.detector_lst = []
		for ch in range(self.ports):
			if self.int_vars[ch].get() == 1:
				self.detector_all_lst[ch]["on"] = True
				self.detector_all_lst[ch]["min"] = float(self.min_vars[ch].get())
				self.detector_all_lst[ch]["max"] = float(self.max_vars[ch].get())
				self.detector_all_lst[ch]["bin"] = float(self.bin_vars[ch].get())
				self.detector_all_lst[ch]["yscale"] =  self.choice_vars[ch].get()
				self.detector_all_lst[ch]["leaf"] =  self.leaf_vars[ch].get()
				self.detector_all_lst[ch]["name"] =  self.name_vars[ch].get()
				
				self.detector_lst.append(self.detector_all_lst[ch])
		
		if self.file_loaded == True:
			self.reload()
		
		self.channel_window.destroy()

	def channel_button2(self):
		""" Viewer Window Button action. Reads entry fields and checkboxes"""
		if is_number(self.refresh_var.get()):
			self.update_interval = float(self.refresh_var.get())
			self.update_var.set("Refresh rate: {}s".format(self.update_interval))
		
		self.safty_var.set(self.safty_var.get())
		
		self.viewer_window.destroy()

	def safty_update(self):
		""" This checks if the loading time is longer the the update time
		and rescales update time accordingly"""
		if self.safty_var.get() == 1:
			if self.update_interval < 2 * self.update_cycle:
				self.update_interval = np.ceil(self.update_cycle * 3)
				print "Increasing Refresh rate", self.update_interval, "s"

if __name__ == "__main__":

	Gui()
