#include <vector>
using namespace std;
void he_check(int runnumber) {
   stringstream s;
   s << std::setw(5) << std::setfill('0') << runnumber << ".root";
   
   
   TFile *f = new TFile(s.str().c_str(),"READ");
   TCanvas * c = new TCanvas("c1","",1800,900);
   c->Divide(1,3);
   
   vector<TH2F*> therawhistos;
   therawhistos.push_back(new TH2F());
   therawhistos.push_back(new TH2F());
   therawhistos.push_back(new TH2F());
   therawhistos.push_back(new TH2F());
   therawhistos.push_back(new TH2F());
   therawhistos.push_back(new TH2F());
   vector<TH1D*> therates;
   therates.push_back(new TH1D());
   therates.push_back(new TH1D());
   therates.push_back(new TH1D());
   therates.push_back(new TH1D());
   therates.push_back(new TH1D());
   therates.push_back(new TH1D());
   vector<TH1D*> theenergy;
   theenergy.push_back(new TH1D());
   theenergy.push_back(new TH1D());
   theenergy.push_back(new TH1D());
   theenergy.push_back(new TH1D());
   theenergy.push_back(new TH1D());
   theenergy.push_back(new TH1D());
   
   
   vector<string> thenames;
   thenames.push_back("hist_0");  
   thenames.push_back("hist_1");
   thenames.push_back("hist_2");
   thenames.push_back("hist_3");
   thenames.push_back("hist_4");
   thenames.push_back("hist_5");
   
   
   while(1){   
	   
	   //First Get 6 Raw Histograms
	   for(int i=0; i<6; i++){
			f->ReadKeys();
			stringstream myname;
			myname << "test_" << i;
			delete f->FindObject(thenames[i].c_str());
			TH2F * h;
			f->GetObject(thenames[i].c_str(),h);
			if(!h) {
				cout << "PROBLEM HERE" << endl;
				continue;
			}
	        therawhistos[i] = h->Clone(myname.str().c_str());
		}

		therates[0]->Delete();
		theenergy[0]->Delete();
		theenergy[1]->Delete();

		{
		TH1D * test = therawhistos[2]->ProjectionX("Rate_Det_1",therawhistos[2]->GetYaxis()->FindBin(12000),therawhistos[2]->GetYaxis()->GetXmax(),"");
			test->SetTitle("Rate of Current (Ch 2");
			therates[0] = (TH1D*) test->Clone("Rate_Det_1");
		}	
		
		
		{

		TH1D * test = therawhistos[0]->ProjectionY("Eng_Det_1",0,therawhistos[0]->GetXaxis()->GetXmax(),"");
		test->SetTitle("Energy of NICE (Ch 0)");
		theenergy[0] = (TH1D*) test->Clone("Eng_Det_1");
		theenergy[0]->GetXaxis()->SetRangeUser(2000,70000);
		}
		
		
		
		
		{
		TH1D * test2 = therawhistos[2]->ProjectionY("Eng_Det_2",0,therawhistos[2]->GetXaxis()->GetXmax(),"");
			test2->SetTitle("Int. current (Ch 2)");
			theenergy[1] = (TH1D*) test2->Clone("Eng_Det_2");
			theenergy[1]->GetXaxis()->SetRangeUser(1000,10000);
		}	



		c->cd(1);
		therates[0]->Draw("");
		//~ therawhistos[0]->Draw("colz");
		c->cd(2);
		//~ therates[1]->Draw("");
		//~ gpad -> SetLogy();
		theenergy[0]->Draw("");
		gPad->SetLogy();
		
		c->cd(3);
		//~ gPad->SetLogy();
		theenergy[1]->Draw("");

		c->Update();
		gSystem->Sleep ( 5000 );
		cout << "UPDATING NOW" << endl;

	   //~ cout << name << "\t" << s.str() << endl;
	   //~ if(!h) cout << "couldn't find histogram" << endl;
	   //~ h->Draw("colz");
	   //~ c->Update();
	   //~ gSystem->Sleep ( 10000 );
   }
}
