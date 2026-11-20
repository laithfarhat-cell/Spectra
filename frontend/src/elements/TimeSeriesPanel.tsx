import React, {useMemo} from 'react';
import ReactECharts from './ECharts';
import type {PanelProps} from './ElementRegistry';
export default function TimeSeriesPanel({data,config={},onDrillDown}:PanelProps){
 const timeKey=config.time??'timestamp';
 const keys=(config.values as string[]|undefined)??Object.keys(data[0]??{}).filter(k=>k!==timeKey&&typeof data[0]?.[k]==='number').slice(0,4);
 const option=useMemo(()=>{
  const times=data.map((r,i)=>{const t=r[timeKey];return t?new Date(typeof t==='number'&&t<1e12?t*1000:t).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'}):String(i)});
  return {tooltip:{trigger:'axis',backgroundColor:'#111827',borderColor:'#283548',textStyle:{color:'#e2e8f0'}},grid:{left:38,right:16,top:18,bottom:28},xAxis:{type:'category',boundaryGap:false,data:times,axisLabel:{color:'#64748b',fontSize:10},axisLine:{lineStyle:{color:'#243244'}}},yAxis:{type:'value',axisLabel:{color:'#64748b',fontSize:10},splitLine:{lineStyle:{color:'#1d2939'}}},dataZoom:[{type:'inside'},{type:'slider',height:12,bottom:2,borderColor:'transparent',backgroundColor:'#111827',fillerColor:'#26364a'}],series:keys.map((key,i)=>{
   const values=data.map(r=>Number(r[key])||0), mean=values.length?values.reduce((a,b)=>a+b,0)/values.length:0, std=values.length?Math.sqrt(values.reduce((a,b)=>a+(b-mean)**2,0)/values.length):0;
   const anomalies=std?values.flatMap((value,index)=>Math.abs(value-mean)>2.5*std?[{coord:[index,value],value}]:[]):[];
   return {name:key,type:'line',smooth:true,symbol:'none',sampling:'lttb',lineStyle:{width:2},areaStyle:{opacity:i===0?.08:0},data:values,...(i===0?{itemStyle:{color:'#52d6bb'},...(std?{markArea:{silent:true,itemStyle:{color:'rgba(243,184,91,.08)'},data:[[{yAxis:mean-2*std},{yAxis:mean+2*std}]]}}:{})}: {itemStyle:{color:['#8296ff','#f3b85b','#ef7188'][i%3]}}),...(anomalies.length?{markPoint:{symbol:'circle',symbolSize:8,itemStyle:{color:'#f3b85b'},data:anomalies}}:{})};
  })};
 },[data,keys,timeKey]);
 return <div className="chart-wrap" onDoubleClick={()=>keys[0]&&data.length&&onDrillDown?.(keys[0],data.at(-1)?.[keys[0]])}><ReactECharts option={option} style={{height:'100%',minHeight:180}} notMerge lazyUpdate/></div>;
}
