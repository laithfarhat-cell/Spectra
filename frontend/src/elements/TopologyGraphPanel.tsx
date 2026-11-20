import React, {useMemo} from 'react';
import ReactECharts from './ECharts';
import type {PanelProps} from './ElementRegistry';
export default function TopologyGraphPanel({data,config={},onDrillDown}:PanelProps){
 const source=config.source??'source', target=config.target??'target', weight=config.weight??'value';
 const option=useMemo(()=>{const names=new Set<string>(); data.forEach(r=>{if(r[source]!=null)names.add(String(r[source]));if(r[target]!=null)names.add(String(r[target]))});const nodes=[...names].map((name,i)=>({name,symbolSize:Math.max(14,Math.min(35,18+(data.filter(r=>String(r[source])===name||String(r[target])===name).length*2))),itemStyle:{color:['#54d5b7','#8296ff','#f3b85b','#ec7189'][i%4]}}));const links=data.filter(r=>r[source]!=null&&r[target]!=null).slice(0,300).map(r=>({source:String(r[source]),target:String(r[target]),value:Number(r[weight])||1}));return {tooltip:{},series:[{type:'graph',layout:'force',roam:true,draggable:true,data:nodes,links,force:{repulsion:160,edgeLength:90},label:{show:true,color:'#a8b7c9',fontSize:10},lineStyle:{color:'#46566d',curveness:.15,opacity:.65},emphasis:{focus:'adjacency'}}]};},[data,source,target,weight]);
 return <div onClick={(e:any)=>{const name=e?.target?.name;if(name)onDrillDown?.(source,name)}}><ReactECharts option={option} style={{height:'100%',minHeight:180}} notMerge lazyUpdate/></div>;
}
