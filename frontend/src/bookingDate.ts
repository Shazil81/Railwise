/** Timetable day 1 is the train's origin date, not necessarily the boarding date. */
export function boardingDate(originDate:string,stopDay:number):string {
  const date=new Date(`${originDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate()+stopDay-1);
  return date.toISOString().slice(0,10);
}
