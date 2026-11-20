import React from 'react';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import {LineChart,GraphChart,GaugeChart,HeatmapChart,ScatterChart,SankeyChart} from 'echarts/charts';
import {GridComponent,TooltipComponent,DataZoomComponent,VisualMapComponent,MarkAreaComponent,MarkPointComponent} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';

echarts.use([LineChart,GraphChart,GaugeChart,HeatmapChart,ScatterChart,SankeyChart,GridComponent,TooltipComponent,DataZoomComponent,VisualMapComponent,MarkAreaComponent,MarkPointComponent,CanvasRenderer]);
export default function ECharts(props:React.ComponentProps<typeof ReactEChartsCore>){return <ReactEChartsCore echarts={echarts} {...props}/>}
