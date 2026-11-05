export function stationCode(value: string): string {
  const text = value.trim();
  return (text.match(/\(([A-Za-z0-9]{1,10})\)$/)?.[1] || (/^[A-Za-z0-9]{1,10}$/.test(text) ? text : '')).toUpperCase();
}
export interface StationChoice { code: string; name: string }
export interface StationSearchResult {
  stations: StationChoice[]; requires_selection?: boolean; is_city?: boolean;
  terminal_group?: {name:string;codes:string[]}|null;
}
export function resolveSearchEndpoint(value:string,data:StationSearchResult,includeNearby=true) {
  if(includeNearby && data.is_city && data.terminal_group) {
    return {code:value.trim(),display:data.terminal_group.name};
  }
  if(data.requires_selection&&!data.stations.some(station=>station.code===stationCode(value))) {
    throw Error('This city has several stations. Choose a station, or enable nearby city terminals.');
  }
  const station=resolveStationChoice(value,data.stations);
  if(!station)throw Error('Choose a station from suggestions, or a supported city with nearby terminals enabled.');
  return {code:station.code,display:`${station.name} (${station.code})`};
}
export function resolveStationChoice(value: string, choices: StationChoice[], allowNameResolution = true): StationChoice | null {
  const code = stationCode(value);
  const byCode = choices.find(choice => choice.code.toUpperCase() === code);
  if (byCode) return byCode;
  if (!allowNameResolution) return null;
  const normalize = (name: string) => name.trim().toLowerCase().replace(/\s+(jn|junction)\.?$/, '').replace(/\s+/g, ' ');
  const matches = choices.filter(choice => normalize(choice.name) === normalize(value));
  return matches.length === 1 ? matches[0] : null;
}
export function indiaToday(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
}
