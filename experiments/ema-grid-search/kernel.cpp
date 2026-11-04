#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

// Reads one cached MOEX candle series on stdin. Output is one row per pair/mode.
// Fill and sizing rules mirror src/scan_ema.py; open positions are marked to market.
struct Bar { std::string ts; double open, close; };
struct Result { int trades=0, wins=0; double net=0, hold=0, pf=0, dd=0; };

Result run(const std::vector<Bar>& b, const std::vector<double>& ef,
           const std::vector<double>& es, int slow, int start_index,
           double fee, double slip, double tick, int mode) {
    Result r;
    if ((int)b.size() < slow+3) return r;
    double capital=1000000, cash=capital, entry=0, peak=capital;
    int pos=0; double first=0, last=0, gp=0, gl=0;
    for (int i=std::max(slow,start_index); i<(int)b.size(); ++i) {
        if (!first) first=b[i].open;
        last=b[i].close;
        bool up=ef[i-2]<=es[i-2] && ef[i-1]>es[i-1];
        bool down=ef[i-2]>=es[i-2] && ef[i-1]<es[i-1];
        double signal_equity=cash+pos*b[i-1].close;
        int qty=(int)std::floor(signal_equity*0.25/b[i-1].close);
        double pnl=0; bool closed=false;
        if (pos>0 && down) {
            double proceeds=pos*std::max(b[i].open*(1-slip)-tick,0.0)*(1-fee);
            pnl=proceeds-entry; cash+=proceeds; pos=0; closed=true;
        } else if (pos<0 && up) {
            double cover=-pos*(b[i].open*(1+slip)+tick)*(1+fee);
            pnl=entry-cover; cash-=cover; pos=0; closed=true;
        }
        if (closed) { ++r.trades; if(pnl>0) {++r.wins; gp+=pnl;} else if(pnl<0) gl-=pnl; }
        if (pos==0 && qty>0 && ((up && mode!=1)||(down && mode!=0))) {
            if (up) {
                entry=qty*(b[i].open*(1+slip)+tick)*(1+fee);
                if (entry<=cash) {cash-=entry; pos=qty;}
            } else {
                entry=qty*std::max(b[i].open*(1-slip)-tick,0.0)*(1-fee);
                cash+=entry; pos=-qty;
            }
        }
        double equity=cash+pos*b[i].close;
        peak=std::max(peak,equity);
        r.dd=std::min(r.dd,100*(equity/peak-1));
    }
    r.net=100*((cash+pos*(last?last:b.back().close))/capital-1);
    r.pf=gl ? gp/gl : (gp ? INFINITY : 0);
    if (first) {
        int q=(int)std::floor(capital*0.25/first);
        double cost=q*(first*(1+slip)+tick)*(1+fee);
        double value=q*std::max(last*(1-slip)-tick,0.0)*(1-fee);
        r.hold=100*(value-cost)/capital;
    }
    return r;
}

int main(int argc,char** argv) {
    if(argc!=7) return 2;
    std::string train=argv[1], oos=argv[2];
    double fee=std::atof(argv[3])/10000, slip=std::atof(argv[4])/10000;
    double tick=std::atof(argv[5]); int maxp=std::atoi(argv[6]);
    std::vector<Bar> b; std::string line;
    while(std::getline(std::cin,line)) {
        std::istringstream in(line); Bar x; std::string op,cl;
        if(std::getline(in,x.ts,',') && std::getline(in,op,',') && std::getline(in,cl,',')) {
            x.open=std::atof(op.c_str()); x.close=std::atof(cl.c_str());
            if(x.open>0 && x.close>0) b.push_back(x);
        }
    }
    if(b.empty()) return 0;
    int train_index=0, oos_index=0;
    while(train_index<(int)b.size() && b[train_index].ts.substr(0,10)<train) ++train_index;
    while(oos_index<(int)b.size() && b[oos_index].ts.substr(0,10)<oos) ++oos_index;
    std::vector<std::vector<double>> e(maxp+1,std::vector<double>(b.size()));
    for(int p=2;p<=maxp;++p) {
        double a=2.0/(p+1); e[p][0]=b[0].close;
        for(size_t i=1;i<b.size();++i) e[p][i]=e[p][i-1]+a*(b[i].close-e[p][i-1]);
    }
    std::cout<<std::fixed<<std::setprecision(4);
    for(int f=2;f<maxp;++f) for(int s=f+1;s<=maxp;++s) for(int m=0;m<3;++m) {
        Result a=run(b,e[f],e[s],s,train_index,fee,slip,tick,m);
        Result z=run(b,e[f],e[s],s,oos_index,fee,slip,tick,m);
        std::cout<<f<<','<<s<<','<<m<<','<<b.size()<<','<<a.trades<<','<<a.wins<<','
                 <<a.net<<','<<a.hold<<','<<a.pf<<','<<a.dd<<','<<z.trades<<','
                 <<z.wins<<','<<z.net<<','<<z.hold<<','<<z.pf<<','<<z.dd<<'\n';
    }
}
