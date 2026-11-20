import React from 'react';import{createRoot}from'react-dom/client';import DashboardCanvas from './components/DashboardCanvas';import './styles.css';import 'react-grid-layout/css/styles.css';import 'react-resizable/css/styles.css';
createRoot(document.getElementById('root')!).render(<React.StrictMode><DashboardCanvas/></React.StrictMode>);
