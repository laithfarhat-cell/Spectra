import React, {lazy} from 'react';
export type SchemaColumn = {name:string; type?:string; semantic?:string; statistics?:Record<string,number|null>};
export type PanelProps = {data:Record<string, any>[]; schema?:SchemaColumn[]; config?:Record<string, any>; timeRange?:string; onDrillDown?:(field:string,value:any)=>void};

export const ElementRegistry:Record<string,React.ComponentType<PanelProps>> = {
  timeseries:lazy(()=>import('./TimeSeriesPanel')),
  topology:lazy(()=>import('./TopologyGraphPanel')),
  logs:lazy(()=>import('./FacetedLogExplorer')),
  stat:lazy(()=>import('./StatSparklinePanel')),
  gauge:lazy(()=>import('./GaugePanel')),
  heatmap:lazy(()=>import('./HeatmapPanel')),
  table:lazy(()=>import('./SmartDataTable')),
  sankey:lazy(()=>import('./SankeyPanel')),
  geo:lazy(()=>import('./GeoMapPanel')),
};
export const elementMetadata = Object.keys(ElementRegistry).map(type=>({type,label:type[0].toUpperCase()+type.slice(1)}));
export function resolveElement(type:string){return ElementRegistry[type] ?? ElementRegistry.table;}
