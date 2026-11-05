export const berthLabels:Record<string,string>={ANY:'No preference',LB:'Lower',MB:'Middle',UB:'Upper',SL:'Side Lower',SU:'Side Upper',NA:'Seat (no berth)'};
export function berthOptions(travelClass:string) {
  const layouts:Record<string,string[]>={SL:['LB','MB','UB','SL','SU'],'3A':['LB','MB','UB','SL','SU'],'2A':['LB','UB','SL','SU'],'1A':['LB','UB'],CC:[],EC:[]};
  return ['ANY',...(layouts[travelClass]||[])];
}
