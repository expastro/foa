import ROOT
import numpy as np
import time 
from playsound import playsound


import Tkinter as tk
from tkFileDialog import askopenfilename
from tkFileDialog import asksaveasfilename
import tkMessageBox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.figure import Figure 
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

import datetime
import cPickle as pickle
import multiprocessing
import threading
import os

import argparse
parser = argparse.ArgumentParser(description='FOA - Frankfurt Online Analizer')

parser.add_argument('--ports', type = int,  default = 8,\
                    help="Number of histograms in root file. In general equals number of ports on board.")
parser.add_argument('--no_mp', action='store_false',\
                    help="Turn off multi processing. Data reading will block the main process.")
# parser.add_argument('--no_mp', action='store_true',\
                    # help="Turn on multi processing. Data reading will not block the main process.")
args = parser.parse_args()


def is_number(instr):
	try:
		out =float(instr)
		return True
	except:
		return False

def ensure_dir_silent(dir_name):
	"""
	Creates a directory with name 'dir_name'.
	"""
	
	if not os.path.isdir(dir_name):
		os.makedirs(dir_name) 

multi_process = args.no_mp
print "Multiprocessing is set to:", multi_process

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

	def set_cut(self, hist, leaf, min_val, max_val,ch):
		# max_y = hist.GetYaxis().GetBinCenter(hist.GetNbinsY())
		# max_x = hist.GetXaxis().GetBinCenter(hist.GetNbinsX())
		if leaf == "longgate":
			min_y = 0
			min_x = min_val
			max_y = hist.GetYaxis().GetBinCenter(hist.GetNbinsY())
			max_x = max_val
		elif leaf == "t":
			min_y = min_val
			min_x = 0
			max_y = max_val
			max_x = max_x = hist.GetXaxis().GetBinCenter(hist.GetNbinsX())

		cut = ROOT.TCutG("cut_{}".format(ch),5)
		cut.SetPoint(0, min_x,   min_y)
		cut.SetPoint(1, min_x,   max_y)
		cut.SetPoint(2, max_x, max_y)
		cut.SetPoint(3, max_x, min_y)
		cut.SetPoint(4, min_x,   min_y)
		if leaf == "longgate":
			cut_hist = hist.ProjectionY("projection_{}".format(ch),0,-1,"[cut_{}]".format(ch))
		elif leaf == "t":
			cut_hist = hist.ProjectionX("projection_{}".format(ch),0,-1,"[cut_{}]".format(ch))
		return cut_hist

	def get_data(self, leafname, ch, cut_from, cut_to):
		x_lst = []
		y_lst = []
		hist = ROOT.gROOT.FindObject("hist_{}".format(ch))
		
		if leafname == "longgate":
			if cut_from == "":
				hist_proj = hist.ProjectionY()
			else:
				hist_proj = self.set_cut(hist, "longgate", cut_from, cut_to, ch)
		elif leafname == "t":
			if cut_from == "":
				hist_proj = hist.ProjectionX()
			else:
				hist_proj = self.set_cut(hist, "t", cut_from, cut_to, ch)
		else:
			raise ImportError
		
		maxb = hist_proj.GetNbinsX() + 1
		for i in range(0, maxb):
			pos = hist_proj.GetBinCenter(i)
			x_lst.append(pos)
			x_lst.append(pos + hist_proj.GetBinWidth(i))
			
			y_lst.append(hist_proj.GetBinContent(i))
			y_lst.append(hist_proj.GetBinContent(i))
		
		
		return [np.array(x_lst), np.array(y_lst), datetime.datetime.now()]
	
	def get_data_all(self, detector_lst):
		all_out_lst = []
		for det in detector_lst:
			all_out_lst.append(self.get_data(det["leaf"], det["ch"], det["cut_from"], det["cut_to"]))
		
		return all_out_lst


	def close(self):
		self.rfile.Close()

class Gui():
	"""Creates the grahical user interface"""
	def __init__(self):
		"""Creates main window."""
		### init variables
		## default update interval
		self.update_interval = 12
		## load a file for the rest of the program to work
		self.file_loaded = False
		self.ref_time = datetime.datetime.now()
		## init the counts in window
		self.ciw = {}
		## number of channels on DAQ board
		self.ports = args.ports
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
		## initial loading error flag
		self.init_loading = False
		self.init_loading2 = False
		self.init_loading3 = 0
		## alarms
		self.alarm_lst = []
		
		## default vals
		
		for j in range(self.ports):
			self.detector_all_lst.append({"ch" : j, "leaf" : "longgate", "on":False, "yscale" : "linear", "name":"Channel {}".format(j),"cut_from": "", "cut_to": ""})
		## tk and matplotlib variables
		self.data_arr = []
		self.ln = []
		self.lim_dic = {}
		self.colors = ['midnightblue', 'darkorange', 'darkred','darkgreen', 'blueviolet', 'goldenrod', 'darkgray', 'darkolivegreen',\
		'cyan', 'darkmagenta', 'navy', 'maroon'] * 2
		self.int_vars = []
		self.min_vars = []
		self.max_vars = []
		self.bin_vars = []
		self.name_vars = []
		self.choice_vars = []
		self.cut_from_vars = []
		self.cut_to_vars = []
		self.choices = ["linear", "log"]
		self.leaf = ["longgate", "t"]
		self.leaf_vars = []
		self.det_count = 0
		self.update_cycle = 0
		self.skip_to_load = False
		self.alarm_sound_dict = {}
		self.alarm_sound_count = {}
		self.alarm_user_hold = False
		self.play_sound = False
		self.save_time = datetime.datetime(2000,1,1)
		
		
		## debugging var
		self.temp2 = 1
		self.temp = 1
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
		self.auto_xscale_var = tk.IntVar()
		self.safty_var = tk.IntVar()
		self.safty_var.set(1)
		self.stop_refresh = tk.IntVar()
		self.stop_refresh.set(1)
		self.save_pic_var = tk.IntVar()
		self.save_pic_time_var = tk.StringVar()
		self.save_pic_time_var.set("60")


		self.alarm_var = tk.StringVar()
		

		## hard shutdown when pressing the x
		self.root.protocol("WM_DELETE_WINDOW", lambda: self.end())
		
		self.into_msg = """
----------------------Welcome to the Frankfurt Online Analyzer----------------------

1) Choose at least one channel under Options > Channel...

2) Open file under File > Load...                                            
"""
		
		## Intro message
		self.into_label_1 = tk.Label(self.root, text = self.into_msg)
		self.into_label_1.pack(side=tk.TOP, padx = 5, pady = 5, fill = "both")
		

		
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
		elif len(self.detector_lst) <=9:
			self.f, self.ax = plt.subplots(3, 3)
		elif len(self.detector_lst) <=12:
			self.f, self.ax = plt.subplots(4, 3)
		elif len(self.detector_lst) <=16:
			self.f, self.ax = plt.subplots(4, 4)
		else:
			raise SystemExit("Too many detectors!")
		
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
		

		self.ani = FuncAnimation(self.f, self.update, interval = 200, blit=True)
		
	def save_fig(self):
		time_delta = float(self.save_pic_time_var.get())
		pic_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "pics")
		ensure_dir_silent(pic_path)
		if (datetime. datetime.now() - self.save_time ).seconds > time_delta and self.save_pic_var.get() == 1:
			self.f.subplots_adjust(top=0.92)
			self.f.suptitle("{}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), fontsize = 16))
			plt.savefig(os.path.join(pic_path, "foa_save.png"), dpi = 500)
			self.save_time = datetime.datetime.now()
			self.f.subplots_adjust(top=0.97)
			self.f.suptitle("")


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
			
			## save plot

			self.save_fig()

			## reset view if inital loading error
			if self.init_loading == True and self.init_loading2 == True:
				self.init_loading3 +=1
				if self.init_loading3 >= 18 * len(self.detector_lst):
					self.auto_scale_axes()
					self.init_loading = False
					self.init_loading2 = False
					self.init_loading3 = False
		return self.ln

	def auto_scale_axes(self):
		"""Sets limits so all data is displayed"""
		# if len(self.detector_lst) == len(self.data_arr):
		try:
			for i in range(0, len(self.data_arr)):
				max_val_x = np.max(self.data_arr[i][0])
				max_val_y = np.max(self.data_arr[i][1])
				self.ax[i].set_xlim([-1 * max_val_x * 0.05, max_val_x * 1.05])
				self.ax[i].set_ylim([-1 * max_val_y * 0.05, max_val_y* 1.05])
			self.canvas.draw()
			self.init_loading = False
			self.init_loading2 = False
			self.init_loading3 = False
		except:
			print "Error while trying to auto-rescale."

	def auto_xscale(self):
		try:
			for i in range(0, len(self.detector_lst)):
				if self.ax[i].get_xlim() == (0.0, 1.0):
					pass
				else:
					left,right = self.ax[i].get_xlim()
					compare_right = self.data_arr[i][0][np.flatnonzero(self.data_arr[i][1])[-1]]
					if compare_right + 5 <= np.max(self.data_arr[i][0]):
						add_extra_bins = 5
					else:
						add_extra_bins = 0
					if right < compare_right:
						self.ax[i].set_xlim([left, compare_right+ add_extra_bins])
			self.canvas.draw()
		except:
			pass

	def call_root(self, future_result = None):
		""" Loads the ROOT data"""
		start_time = datetime.datetime.now()
		root_instance = LoadRoot(self.filename)
		data_arr_bak = self.data_arr
		self.data_arr = []
		try:
			self.data_arr = root_instance.get_data_all(self.detector_lst)
			# 
			# temp_data = np.ones(100)
			# temp_data[0:self.temp2] = 10
			
			# print self.temp2
			# self.data_arr = [[np.arange(1,101), temp_data, datetime.datetime.now()]]

			
			
			# ~ root_instance.close()
			## time: end of loading process
			self.ref_time = self.data_arr[-1][-1]
			
		except:
			print "Error while loading data. Retry in {}s".format(self.update_interval)
			try:
				if len(data_arr_bak) == 0:
					print "Initial loading error. Displaying junk data. Please wait for next update cycle."
					for i in range(0, len(self.detector_lst)):
						self.data_arr.append([np.arange(1,101), np.ones(100), datetime.datetime.now()])
						self.init_loading = True
						# self.ref_time = datetime.datetime.now()
				else:
					self.data_arr = data_arr_bak
					# self.ref_time = datetime.datetime.now()
			except:
				self.data_arr = [[np.arange(1,101), np.ones(100), datetime.datetime.now()]]
				# self.ref_time = datetime.datetime.now()
		if not future_result ==  None:
			end_time = datetime.datetime.now()
			future_result.put([self.data_arr, (end_time -start_time).total_seconds()])


	def root_data(self, time = False):
		""" Stuff that gets done when new data is loaded """

		if ((datetime.datetime.now() - self.ref_time).total_seconds() > self.update_interval and self.stop_refresh.get() == 1) or time == False:
		## display the loading message. this has to be done with a return 
		## because the loading process blocks the main process and the 
		## message wouldn't be displayed 
			# if self.skip_to_load:
				# self.load_var.set("Loading Data...")
				# self.skip_to_load = False
				# return
			## time: start of loading process
			cycle_start = datetime.datetime.now()
			self.check_alarm()
			if time == False or multi_process == False:
				self.call_root()
				
			else:
				args = []
				kwargs = []
				
				queue= multiprocessing.Queue()

				worker = multiprocessing.Process(target=self.call_root, args = (queue,))
				worker.daemon = True
				worker.start()
				# self.data_arr, self.update_cycle = queue.get()
				def check():
					try:
						self.data_arr, self.update_cycle = queue.get(block=False)
					except:
						self.root.after(200, check)
							
				self.root.after(200, check)
				self.init_loading2 = True

			self.ref_time = datetime.datetime.now()
			self.skip_to_load = True
			
			## time the loading took
			if time == False or multi_process == False:
				self.update_cycle = (self.ref_time - cycle_start).total_seconds()
			else:
				pass
			
			self.safty_update()

			## update the cycle label after each read process
			try:
				self.cycle_var.set("Update cycle: {:.2f}s".format(self.update_cycle))
				self.update_var.set("Refresh rate: {}s".format(self.update_interval))
			except:
				pass
			print "Updated data at {}".format(self.ref_time.strftime("%Y-%m-%d %H:%M:%S"))
			
			## excecute scalings if checked
			self.auto_scale_check()
			self.xscale_check()
			

			
			## next time skipt this if to display load message
			self.load_var.set("")
		else:
			pass



	def end(self):
		""" This kills the program """
		try:
			self.sound_process.terminate()
		except:
			pass
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
		
		alarm_menu = tk.Menu(self.menubar, tearoff = 0)
		self.menubar.add_cascade(label = "Alarm", menu = alarm_menu)
		alarm_menu.add_command(label="Set Alarm...", command = self.alarm_window)

	def menu_bar_ch(self):
		"""Menu Bar Channel windows"""
		## Create a pull-down menu, and add it to the menu bar
		pull_down_menu = tk.Menu(self.menubar_ch, tearoff = 0)
		self.menubar_ch.add_cascade(label = "Settings", menu = pull_down_menu)
		pull_down_menu.add_command(label = "Save...", command = self.channels_save)
		pull_down_menu.add_command(label = "Load...", command = self.channels_load)
		



	def load(self):
		""" Check if Channles are selected before a file is loaded"""
		if len(self.detector_lst) == 0:
			tkMessageBox.showwarning("No Channel selected", "Please activate at least one channel under Options > Channel before loading a file.")
		else:
			self.filename = askopenfilename(defaultextension='.root', title = "Select file", filetypes = [("ROOT files","*.root")])
			self.file_loaded = True
			self.reload()

	def destroyer(self, element):
		try:
			element.destroy()
		except:
			"Error while destroying '{}'".format(str(element))

	def reload(self):
		""" Open a file. If this is not the first file, destroy all plot tk
		elements and empty lists"""
		if len(self.filename) == 0:
			return 
		else:
			try:
				for i in range(0, len(self.detector_lst)):
					self.ax[i].legend_.remove()
			except:
				pass
				
			destroy = []
			
			try:
				self.destroyer(self.canvas.get_tk_widget())
			except:
				pass
			try:
				self.destroyer(self.show_plot)
			except:
				pass
			try:
				self.destroyer(self.fit_button)
			except:
				pass
			try:
				self.destroyer(self.update_label)
			except:
				pass
			try:
				self.destroyer(self.refresh_rate)
			except:
				pass
			try:
				self.destroyer(self.auto_scale_ck)
			except:
				pass
			try:
				self.destroyer(self.auto_xscale_ck)
			except:
				pass
			try:
				self.destroyer(self.stop_refresh_ck)
			except:
				pass

			# reset all parameters
			self.data_arr = []
			self.ciw = {}
			self.ln = []
			self.ax = []
			self.lim_dic = {}
			self.draw_once = True
			self.skip_to_load = False
			self.alarm_sound_dict = {}
			self.alarm_sound_count = {}

			try:
				self.destroyer(self.load_msg)
			except:
				pass
			
			## destroy intro message
			self.into_label_1.destroy()
			
			## set window name to file path
			self.root.title("VdG Viewer" + " " + self.filename)

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

			self.auto_scale_ck = tk.Checkbutton(self.root, text="Auto rescale (beta)", variable=self.auto_scale)
			self.auto_scale_ck.pack(side = tk.LEFT, padx = 5, pady = 5)

			self.auto_xscale_ck = tk.Checkbutton(self.root, text="x-scale (beta)", variable=self.auto_xscale_var)
			self.auto_xscale_ck.pack(side = tk.LEFT, padx = 5, pady = 5)

			self.stop_refresh_ck = tk.Checkbutton(self.root, text="Refresh", variable=self.stop_refresh)
			self.stop_refresh_ck.pack(side = tk.LEFT, padx = 5, pady = 5)
			


	def auto_scale_check(self):
		""" Check if auto scale is checked"""
		if self.auto_scale.get() == 1:
			self.auto_scale_axes()
			print "Rescaled axes"

	def xscale_check(self):
		""" Check if auto scale is checked"""
		if self.auto_xscale_var.get() == 1:
			self.auto_xscale()
			print "Rescaled axes"
			
	def channels_save(self):
		"""Save options of every channel to file"""
		all_options = []
		for ch in range(self.ports):
			single_option = []
			single_option.append(self.int_vars[ch].get())
			single_option.append(self.choice_vars[ch].get())
			single_option.append(self.leaf_vars[ch].get())
			single_option.append(self.name_vars[ch].get())
			single_option.append(self.cut_from_vars[ch].get())
			single_option.append(self.cut_to_vars[ch].get())
			all_options.append(single_option)
		
		ch_save_fn = asksaveasfilename(defaultextension='.chset', title = \
		"Save settings as...", filetypes = [("settings file","*.chset")])
		
		if len(ch_save_fn) == 0:
			pass
		else:
			pickle.dump( all_options, open( ch_save_fn, "wb" ) )

	def channels_load(self):
		"""Save options from file"""
		ch_load_fn = askopenfilename(defaultextension='.chset', \
		title = "Load settings", filetypes = [("settings file","*.chset")])
		if len(ch_load_fn) > 0:
			all_options = pickle.load(open( ch_load_fn, "rb" ) )
			if self.ports > len(all_options):
				run_to = len(all_options)
			else:
				run_to =self.ports
			for ch in range(run_to):
				self.int_vars[ch].set(all_options[ch][0])
				self.choice_vars[ch].set(all_options[ch][1])
				self.leaf_vars[ch].set(all_options[ch][2])
				self.name_vars[ch].set(all_options[ch][3])
				self.cut_from_vars[ch].set(all_options[ch][4])
				self.cut_to_vars[ch].set(all_options[ch][5])
			try:
				self.channel_window.focus_set()
			except:
				pass
		else:
			pass


	
	def channel_window(self):
		""" Window for channel options"""
		self.channel_window = tk.Toplevel()
		self.channel_window.title("Choose Channel")
		
		self.menubar_ch = tk.Menu(self.channel_window)
		self.channel_window.config(menu = self.menubar_ch)
		self.menu_bar_ch()
		
		self.chbuttons = []
		self.choice_entry = []
		self.name_entry = []
		self.leaf_entry = []
		self.cut_from_entry = []
		self.cut_to_entry = []
		
		
		tk.Label(self.channel_window, text="Channel").grid(row = 0, column = 0)
		tk.Label(self.channel_window, text="y-Scale").grid(row = 0, column = 4)
		tk.Label(self.channel_window, text="Leaf").grid(row = 0, column = 5)
		tk.Label(self.channel_window, text="Name").grid(row = 0, column = 6)
		tk.Label(self.channel_window, text="Cut from").grid(row = 0, column = 7)
		tk.Label(self.channel_window, text="Cut to").grid(row = 0, column = 8)
		
		for ch in range(self.ports):
			self.int_vars.append(tk.IntVar())
			self.choice_vars.append(tk.StringVar())
			self.name_vars.append(tk.StringVar())
			self.leaf_vars.append(tk.StringVar())
			self.cut_from_vars.append(tk.StringVar())
			self.cut_to_vars.append(tk.StringVar())
			
			

			self.name_vars[ch].set(self.detector_all_lst[ch]["name"])
			self.choice_vars[ch].set(self.choices[0])
			self.leaf_vars[ch].set(self.leaf[0])
			self.cut_from_vars[ch].set(self.detector_all_lst[ch]["cut_from"])
			self.cut_to_vars[ch].set(self.detector_all_lst[ch]["cut_to"])
			
			self.chbuttons.append(tk.Checkbutton(self.channel_window, text=str(ch), variable=self.int_vars[ch]))
			self.chbuttons[ch].grid(row = ch +1 , column = 0, padx = (5,5), pady = (0,5), sticky = tk.W+tk.E)
			
			self.choice_vars[ch].set(self.detector_all_lst[ch]["yscale"])
			self.choice_entry.append(tk.OptionMenu(self.channel_window, self.choice_vars[ch], *self.choices))
			self.choice_entry[ch].grid(row = ch + 1, column = 4, padx = (5,5), pady = (0,5), sticky = tk.W)
			
			self.leaf_vars[ch].set(self.detector_all_lst[ch]["leaf"])
			self.leaf_entry.append(tk.OptionMenu(self.channel_window, self.leaf_vars[ch], *self.leaf))
			self.leaf_entry[ch].grid(row = ch + 1, column = 5, padx = (5,5), pady = (0,5), sticky = tk.W)

			self.name_entry.append(tk.Entry(self.channel_window, textvariable = self.name_vars[ch], width = 10))
			self.name_entry[ch].grid(row = ch + 1, column = 6, padx = (5,5), pady = (0,5), sticky = tk.W)

			self.cut_from_entry.append(tk.Entry(self.channel_window, textvariable = self.cut_from_vars[ch], width = 10))
			self.cut_from_entry[ch].grid(row = ch + 1, column = 7, padx = (5,5), pady = (0,5), sticky = tk.W)

			self.cut_to_entry.append(tk.Entry(self.channel_window, textvariable = self.cut_to_vars[ch], width = 10))
			self.cut_to_entry[ch].grid(row = ch + 1, column = 8, padx = (5,5), pady = (0,5), sticky = tk.W)
		
		
		self.ch_button = tk.Button(self.channel_window, text='Accept',\
		command = self.channel_button, width = 8)
		self.ch_button.grid(row = 100, column = 0, padx = 10,\
		pady = 10)


	
	
	def viewer_window(self):
		"""Window for viewer options"""
		
		self.viewer_window = tk.Toplevel()
		self.viewer_window.title("Viewer Options")

		
		tk.Label(self.viewer_window, text="Refresh rate:").grid(row = 0, column = 0)
		self.refresh_var.set(str(self.update_interval))
		self.refresh_entry = (tk.Entry(self.viewer_window, textvariable = self.refresh_var, width = 5))
		self.refresh_entry.grid(row = 0, column = 1, padx = (5,0), pady = (0,5), sticky = tk.E)
		tk.Label(self.viewer_window, text="s").grid(row = 0, column = 2, sticky = tk.W)

		
		self.safty_ref_ck = tk.Checkbutton(self.viewer_window, text="Safty refresh", variable=self.safty_var)
		self.safty_ref_ck.grid(row = 1, column = 0, sticky = tk.W)


		self.save_pic_check = tk.Checkbutton(self.viewer_window, text="Save Screenshot", variable=self.save_pic_var)
		self.save_pic_check.grid(row = 2, column = 0, sticky = tk.W)

		self.save_pic_entry = (tk.Entry(self.viewer_window, textvariable = self.save_pic_time_var, width = 5))
		self.save_pic_entry.grid(row = 2, column = 1, padx = (5,0), pady = (0,5), sticky = tk.E)
		tk.Label(self.viewer_window, text="s").grid(row = 2, column = 2, sticky = tk.W)
		
		self.ch_button2 = tk.Button(self.viewer_window, text='Accept',\
		command = self.channel_button2, width = 8)
		self.ch_button2.grid(row = 20, column = 0, padx = 10,\
		pady = 10)

	def sound_alarm(self, ch):
		print "ALARM!"
		self.alarm_user_window(ch)
	
	def check_alarm(self):
		if len(self.data_arr) == 0 or self.alarm_user_hold == True:
			return None
		for i, ach in enumerate(self.alarm_lst):
			for j, ch in enumerate(self.detector_lst):
				if ach["ch"] == ch["ch"]:
					alarm_bin_lst = np.where(self.data_arr[j][1] > ach["y"])[0]
					if len(alarm_bin_lst) == 0:
						break
					else:
						alarm_last = alarm_bin_lst[-1]
						if j in self.alarm_sound_dict:
							if self.data_arr[j][1][alarm_last] >= ach["y"] and not self.alarm_sound_dict[j] == alarm_last:
								self.alarm_sound_dict[j] = alarm_last
								self.alarm_sound_count[j] = 0
							else:
								self.alarm_sound_count[j] += 1
								if self.alarm_sound_count[j] >= ach["x"]:
									self.sound_alarm(j)
								else:
									pass

						else:
							self.alarm_sound_dict[j] = alarm_last
							self.alarm_sound_count[j] = 0

	def alarm_user_window(self, ch):
		"""Window for viewer options"""
		
		self.alarm_user = tk.Toplevel()
		self.alarm_user.title("ALARM!")
		# self.alarm_user.overrideredirect(1)
		self.alarm_user.protocol("WM_DELETE_WINDOW", lambda: alarm_user_close())

		self.alarm_user_hold = True
		try:
			self.alarm_user.focus_set()
		except:
			pass
		class FlashableLabel(tk.Label):
			def flash(self):
				bg = self.cget('background')
				fg = self.cget('foreground')
				self.configure(background=fg,foreground=bg)
				self.after(1000,self.flash) 
		
		def sound():
				while self.play_sound:
					playsound("sounds/alert_short_2.mp3")
					time.sleep(1.5)


		
		# tk.Label(self.alarm_user, text="ALARM in Channel {}".format(ch), fg = "red", font=("Arial", 20)).grid(row = 0, column = 0, sticky = tk.W)
		test = FlashableLabel(self.alarm_user, text="ALARM in Channel {}".format(ch), fg = "red", bg = "black", font=("Arial", 40))
		test.grid(row = 0, column = 0, sticky = tk.W, padx = 2, pady = 2, columnspan=2)
		test.flash()
		
		self.play_sound = True
		self.sound_process = multiprocessing.Process(target = sound)
		self.sound_process.start()


		def alarm_user_close():
			self.alarm_user_hold = False
			self.sound_process.terminate()
			self.play_sound = False
			self.alarm_user.destroy()
		
		self.alarm_user_button = tk.Button(self.alarm_user, text='Ok',\
		command = alarm_user_close, width = 8)
		self.alarm_user_button.grid(row = 1, column = 0, padx = 10,\
		pady = 10)

		def alarm_user_reset():
			self.alarm_user_hold = False
			self.play_sound = False
			self.sound_process.terminate()
			self.alarm_sound_dict = {}
			self.alarm_sound_count = {}
			self.alarm_user.destroy()
		
		self.alarm_user_reset = tk.Button(self.alarm_user, text='Ok and Reset',\
		command = alarm_user_reset, width = 8)
		self.alarm_user_reset.grid(row = 1, column = 1, padx = 10,\
		pady = 10)

	def alarm_window(self):
		"""Window for viewer options"""
		
		if len(self.detector_lst) > 0:
			self.alarm_window = tk.Toplevel()
			self.alarm_window.title("Set Alarm")
			
			try:
				self.alarm_window.focus_set()
			except:
				pass

			self.alarm_status_label()
			
			name_lst = [x[0] for x in self.alarm_lst_temp]
			self.alarm_var.set(name_lst[0])
			alarm_menu = tk.OptionMenu(self.alarm_window, self.alarm_var, *name_lst)
			alarm_menu.grid(row = 1, column = 0,padx = 10, sticky = tk.W)


			self.alarm_var.trace("w", self.alarm_set_frame_func)


			def alarm_close():
				self.alarm_window.destroy()

			self.alarm_button = tk.Button(self.alarm_window, text='Close',\
			command = alarm_close, width = 8)
			self.alarm_button.grid(row = 5, column = 0, padx = 10,\
			pady = 10)

		else:
			tkMessageBox.showwarning("No Channel selected", "Please activate at least one channel under Options > Channel before loading a file.")

	def alarm_status_label(self):
		self.alarm_lst_temp = []
		try:
			for child in self.alarm_status_frame.winfo_children():
				child.destroy()
			self.alarm_status_frame.destroy()
		except:
			pass
		self.alarm_status_frame = tk.LabelFrame(self.alarm_window, text="Status")
		self.alarm_status_frame.grid(row = 0, column = 0,  padx = 10,  pady = 10)
		for el in self.detector_lst:
			status = False
			for alarm_el in self.alarm_lst:
				if el["ch"] == alarm_el["ch"] and alarm_el["status"] == True: 
					status = True
					break
			self.alarm_lst_temp.append(['Channel {}: "{}"'.format(el["ch"], el["name"]), status])
		for i, el in enumerate(self.alarm_lst_temp):
			if el[1] == True:
				col = "green"
				txt = "On"
			else:
				col = "red"
				txt = "Off"
			tk.Label(self.alarm_status_frame, text="{:50}\t{:>4}".format(el[0], txt), fg = col).grid(row = i, column = 0, sticky = tk.W)

	def alarm_set_frame_func(self, *args):
		try:
			self.alarm_set_frame.destroy()
		except:
			pass

		channel = int(self.alarm_var.get().split(":")[0].split()[1])
		self.alarm_set_frame = tk.LabelFrame(self.alarm_window, text="Set alarm")
		self.alarm_set_frame.grid(row = 2, column = 0,  padx = 10,  pady = 10, sticky = tk.W)

		self.alarm_check_var = tk.IntVar()
		c = tk.Checkbutton(self.alarm_set_frame, text="Turn alarm ON", variable=self.alarm_check_var)
		c.grid(row = 0, column = 0, sticky = tk.W)

		self.y_cutoff_var = tk.StringVar()
		y_cutoff = tk.Entry(self.alarm_set_frame, textvariable = self.y_cutoff_var, width = 12)
		y_cutoff.grid(row = 1, column = 0, sticky = tk.W, pady = 5, padx = 5)
		tk.Label(self.alarm_set_frame, text="Threshold").grid(row = 1, column = 1, sticky = tk.W, pady = 5)

		self.x_cutoff_var = tk.StringVar()
		x_cutoff = tk.Entry(self.alarm_set_frame, textvariable = self.x_cutoff_var, width = 12)
		x_cutoff.grid(row = 2, column = 0, sticky = tk.W, pady = 5, padx = 5)
		tk.Label(self.alarm_set_frame, text="# Refreshes").grid(row = 2, column = 1, sticky = tk.W, pady = 5)

		for k, el in enumerate(self.alarm_lst):
			if el["ch"] == channel:
				self.alarm_check_var.set(1)
				self.y_cutoff_var.set(str(el["y"]))
				self.x_cutoff_var.set(str(el["x"]))


		self.alarm_accept_button = tk.Button(self.alarm_set_frame, text='Accept',\
		command = lambda: self.alarm_accept(channel), width = 8)
		self.alarm_accept_button.grid(row = 2, column = 3, padx = 10,\
		pady = 5)


	def alarm_accept(self, channel):
		valid = True
		if self.alarm_check_var.get() == 1:
			try:
				y_cut = float(self.y_cutoff_var.get())
			except:
				valid = False
				tkMessageBox.showwarning("Invalid entry", "Please use only float values for Threshold input.")
			try:
				x_cut = int(self.x_cutoff_var.get())
			except:
				valid = False
				tkMessageBox.showwarning("Invalid entry", "Please use only integer values for # Refreshes input.")

		for k, el in enumerate(self.alarm_lst):
			if el["ch"] == channel:
				del self.alarm_lst[k]

		if self.alarm_check_var.get() == 1 and valid == True :
			self.alarm_lst.append({"ch": channel, "status": True, "x": x_cut, "y": y_cut})

			# for c in self.alarm_status_frame.winfo_children():
			# 	c.destroy()
			# tk.Label(self.alarm_status_frame, text="1", ).grid(row = 0, column = 0, sticky = tk.W)
		self.alarm_status_label()


	def channel_button(self):
		""" Channel Window Button action. Reads entry fields and checkboxes"""
		self.detector_lst = []
		for ch in range(self.ports):
			if self.int_vars[ch].get() == 1:
				self.detector_all_lst[ch]["on"] = True
				self.detector_all_lst[ch]["yscale"] =  self.choice_vars[ch].get()
				self.detector_all_lst[ch]["leaf"] =  self.leaf_vars[ch].get()
				self.detector_all_lst[ch]["name"] =  self.name_vars[ch].get()
				cut_from = self.cut_from_vars[ch].get()
				if is_number(cut_from):
					self.detector_all_lst[ch]["cut_from"] =  float(cut_from)
				elif cut_from == "":
					self.detector_all_lst[ch]["cut_from"] =  ""
				else:
					print "No cut set! Use only float values for cuts!"
					self.detector_all_lst[ch]["cut_from"] =  ""
				cut_to = self.cut_to_vars[ch].get()
				if is_number(cut_to):
					self.detector_all_lst[ch]["cut_to"] =  float(cut_to)
				elif cut_to == "":
					self.detector_all_lst[ch]["cut_to"] =  ""
				else:
					print "No cut set! Use only float values for cuts!"
					self.detector_all_lst[ch]["cut_to"] =  ""
				
				if cut_from == "" and not cut_to == "":
					self.detector_all_lst[ch]["cut_to"] =  ""
					print "No cut set! Invalid cut combination!"
				if cut_to == "" and not cut_from == "":
					self.detector_all_lst[ch]["cut_from"] =  ""
					print "No cut set! Invalid cut combination!"
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

		if is_number(self.save_pic_time_var.get()):
			self.save_pic_time_var.set(float(self.save_pic_entry.get()))
		
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
