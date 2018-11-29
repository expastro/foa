import ROOT
import time 

def testfile(nbr):
	hist = ROOT.TH2F("hist_0", "hist_0", 150, 0, 150, nbr, 0 ,nbr - 1)
	for i  in range(0, 4096):
		hist.SetBinContent(i, i, 1)
	return hist

n = 200

while True:
	print "writing", n
	outfile = ROOT.TFile("testdata2.root",'recreate')
	h = testfile(n)
	h.Write()
	hists = []

	outfile.Close()
	n += 50
	time.sleep(10)
