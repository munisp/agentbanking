import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Reporting Engine for Remittance Platform
Generates comprehensive reports with charts, analytics, and export capabilities
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import io
import base64

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("transaction-types-distribution")
app.include_router(metrics_router)

from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import httpx
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Integer, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import aioredis
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder
import plotly.io as pio
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
import xlsxwriter
from jinja2 import Environment, FileSystemLoader, Template

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/reporting")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ReportType(str, Enum):
    TRANSACTION_SUMMARY = "transaction_summary"
    AGENT_PERFORMANCE = "agent_performance"
    CUSTOMER_ANALYTICS = "customer_analytics"
    FINANCIAL_OVERVIEW = "financial_overview"
    FRAUD_ANALYSIS = "fraud_analysis"
    COMPLIANCE_REPORT = "compliance_report"
    OPERATIONAL_METRICS = "operational_metrics"
    CUSTOM_REPORT = "custom_report"

class ReportFormat(str, Enum):
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"
    HTML = "html"

class ReportFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ON_DEMAND = "on_demand"

class ReportStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    SCHEDULED = "scheduled"

@dataclass
class ReportParameters:
    start_date: datetime
    end_date: datetime
    customer_ids: Optional[List[str]] = None
    agent_ids: Optional[List[str]] = None
    transaction_types: Optional[List[str]] = None
    include_charts: bool = True
    include_summary: bool = True
    include_details: bool = True
    group_by: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None

class ReportDefinition(Base):
    __tablename__ = "report_definitions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text)
    report_type = Column(String, nullable=False)
    parameters = Column(JSON)
    template_config = Column(JSON)
    frequency = Column(String, default=ReportFrequency.ON_DEMAND.value)
    is_active = Column(Boolean, default=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ReportExecution(Base):
    __tablename__ = "report_executions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    report_definition_id = Column(String, nullable=False)
    report_name = Column(String, nullable=False)
    report_type = Column(String, nullable=False)
    parameters = Column(JSON)
    format = Column(String, nullable=False)
    status = Column(String, default=ReportStatus.PENDING.value)
    file_path = Column(String)
    file_size = Column(Integer)
    error_message = Column(Text)
    execution_time = Column(Float)  # in seconds
    requested_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    report_definition_id = Column(String, nullable=False)
    frequency = Column(String, nullable=False)
    next_execution = Column(DateTime, nullable=False)
    last_execution = Column(DateTime)
    recipients = Column(JSON)  # Email addresses
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

class ReportingService:
    def __init__(self):
        self.redis_client = None
        self.transaction_service_url = os.getenv("TRANSACTION_SERVICE_URL", "http://localhost:8010")
        self.customer_service_url = os.getenv("CUSTOMER_SERVICE_URL", "http://localhost:8011")
        self.fraud_service_url = os.getenv("FRAUD_SERVICE_URL", "http://localhost:8012")
        
        # Initialize Jinja2 for HTML templates
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        os.makedirs(template_dir, exist_ok=True)
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))
        
        # Create default templates
        self.create_default_templates()
    
    async def initialize(self):
        """Initialize the reporting service"""
        try:
            # Initialize Redis for caching
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.redis_client = await aioredis.from_url(redis_url)
            
            logger.info("Reporting Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Reporting Service: {e}")
            self.redis_client = None
    
    def create_default_templates(self):
        """Create default HTML templates for reports"""
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        
        # Transaction Summary Report Template
        transaction_summary_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ report_title }}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { text-align: center; margin-bottom: 30px; }
                .summary-stats { display: flex; justify-content: space-around; margin: 20px 0; }
                .stat-card { text-align: center; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
                .chart-container { margin: 20px 0; text-align: center; }
                table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                .footer { margin-top: 30px; text-align: center; font-size: 12px; color: #666; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{{ report_title }}</h1>
                <p>Period: {{ start_date }} to {{ end_date }}</p>
                <p>Generated: {{ generated_at }}</p>
            </div>
            
            {% if summary_stats %}
            <div class="summary-stats">
                <div class="stat-card">
                    <h3>{{ summary_stats.total_transactions }}</h3>
                    <p>Total Transactions</p>
                </div>
                <div class="stat-card">
                    <h3>${{ "%.2f"|format(summary_stats.total_amount) }}</h3>
                    <p>Total Amount</p>
                </div>
                <div class="stat-card">
                    <h3>${{ "%.2f"|format(summary_stats.average_amount) }}</h3>
                    <p>Average Amount</p>
                </div>
            </div>
            {% endif %}
            
            {% if charts %}
            <div class="chart-container">
                {% for chart in charts %}
                <div>
                    <h3>{{ chart.title }}</h3>
                    <img src="data:image/png;base64,{{ chart.image }}" alt="{{ chart.title }}" />
                </div>
                {% endfor %}
            </div>
            {% endif %}
            
            {% if transaction_details %}
            <h2>Transaction Details</h2>
            <table>
                <thead>
                    <tr>
                        <th>Transaction ID</th>
                        <th>Date</th>
                        <th>Customer</th>
                        <th>Type</th>
                        <th>Amount</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for txn in transaction_details %}
                    <tr>
                        <td>{{ txn.transaction_id }}</td>
                        <td>{{ txn.created_at }}</td>
                        <td>{{ txn.customer_id }}</td>
                        <td>{{ txn.transaction_type }}</td>
                        <td>${{ "%.2f"|format(txn.amount) }}</td>
                        <td>{{ txn.status }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% endif %}
            
            <div class="footer">
                <p>Generated by Remittance Platform Reporting Engine</p>
            </div>
        </body>
        </html>
        """
        
        with open(os.path.join(template_dir, 'transaction_summary.html'), 'w') as f:
            f.write(transaction_summary_template)
        
        # Agent Performance Report Template
        agent_performance_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ report_title }}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { text-align: center; margin-bottom: 30px; }
                .agent-card { border: 1px solid #ddd; margin: 15px 0; padding: 15px; border-radius: 5px; }
                .performance-metrics { display: flex; justify-content: space-between; }
                .metric { text-align: center; }
                table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{{ report_title }}</h1>
                <p>Period: {{ start_date }} to {{ end_date }}</p>
                <p>Generated: {{ generated_at }}</p>
            </div>
            
            {% if agent_performance %}
            <h2>Agent Performance Summary</h2>
            <table>
                <thead>
                    <tr>
                        <th>Agent ID</th>
                        <th>Transactions</th>
                        <th>Total Amount</th>
                        <th>Commission Earned</th>
                        <th>Average Transaction</th>
                        <th>Success Rate</th>
                    </tr>
                </thead>
                <tbody>
                    {% for agent in agent_performance %}
                    <tr>
                        <td>{{ agent.agent_id }}</td>
                        <td>{{ agent.transaction_count }}</td>
                        <td>${{ "%.2f"|format(agent.total_amount) }}</td>
                        <td>${{ "%.2f"|format(agent.commission_earned) }}</td>
                        <td>${{ "%.2f"|format(agent.average_amount) }}</td>
                        <td>{{ "%.1f"|format(agent.success_rate * 100) }}%</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% endif %}
            
            <div class="footer">
                <p>Generated by Remittance Platform Reporting Engine</p>
            </div>
        </body>
        </html>
        """
        
        with open(os.path.join(template_dir, 'agent_performance.html'), 'w') as f:
            f.write(agent_performance_template)
    
    async def generate_report(self, report_type: ReportType, parameters: ReportParameters,
                            format: ReportFormat, requested_by: str) -> str:
        """Generate a report and return execution ID"""
        execution_id = str(uuid.uuid4())
        
        # Create execution record
        db = SessionLocal()
        try:
            execution = ReportExecution(
                id=execution_id,
                report_definition_id="",  # For on-demand reports
                report_name=f"{report_type.value}_report",
                report_type=report_type.value,
                parameters=asdict(parameters),
                format=format.value,
                status=ReportStatus.PENDING.value,
                requested_by=requested_by
            )
            
            db.add(execution)
            db.commit()
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create execution record: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
        
        # Generate report asynchronously
        asyncio.create_task(self._generate_report_async(execution_id, report_type, parameters, format))
        
        return execution_id
    
    async def _generate_report_async(self, execution_id: str, report_type: ReportType,
                                   parameters: ReportParameters, format: ReportFormat):
        """Generate report asynchronously"""
        start_time = datetime.utcnow()
        
        db = SessionLocal()
        try:
            # Update status to generating
            execution = db.query(ReportExecution).filter(ReportExecution.id == execution_id).first()
            if not execution:
                return
            
            execution.status = ReportStatus.GENERATING.value
            db.commit()
            
            # Generate report data
            report_data = await self._collect_report_data(report_type, parameters)
            
            # Generate report file
            file_path = await self._generate_report_file(report_data, format, execution_id)
            
            # Update execution record
            execution.status = ReportStatus.COMPLETED.value
            execution.file_path = file_path
            execution.completed_at = datetime.utcnow()
            execution.execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            if file_path and os.path.exists(file_path):
                execution.file_size = os.path.getsize(file_path)
            
            db.commit()
            
        except Exception as e:
            # Update execution record with error
            execution = db.query(ReportExecution).filter(ReportExecution.id == execution_id).first()
            if execution:
                execution.status = ReportStatus.FAILED.value
                execution.error_message = str(e)
                execution.completed_at = datetime.utcnow()
                execution.execution_time = (datetime.utcnow() - start_time).total_seconds()
                db.commit()
            
            logger.error(f"Report generation failed: {e}")
        finally:
            db.close()
    
    async def _collect_report_data(self, report_type: ReportType, parameters: ReportParameters) -> Dict[str, Any]:
        """Collect data for report generation"""
        report_data = {
            "report_type": report_type.value,
            "parameters": asdict(parameters),
            "generated_at": datetime.utcnow().isoformat(),
        }
        
        if report_type == ReportType.TRANSACTION_SUMMARY:
            report_data.update(await self._collect_transaction_summary_data(parameters))
        elif report_type == ReportType.AGENT_PERFORMANCE:
            report_data.update(await self._collect_agent_performance_data(parameters))
        elif report_type == ReportType.CUSTOMER_ANALYTICS:
            report_data.update(await self._collect_customer_analytics_data(parameters))
        elif report_type == ReportType.FINANCIAL_OVERVIEW:
            report_data.update(await self._collect_financial_overview_data(parameters))
        elif report_type == ReportType.FRAUD_ANALYSIS:
            report_data.update(await self._collect_fraud_analysis_data(parameters))
        elif report_type == ReportType.COMPLIANCE_REPORT:
            report_data.update(await self._collect_compliance_data(parameters))
        elif report_type == ReportType.OPERATIONAL_METRICS:
            report_data.update(await self._collect_operational_metrics_data(parameters))
        
        return report_data
    
    async def _collect_transaction_summary_data(self, parameters: ReportParameters) -> Dict[str, Any]:
        """Collect transaction summary data"""
        try:
            # Call transaction history service
            async with httpx.AsyncClient() as client:
                filter_data = {
                    "start_date": parameters.start_date.isoformat(),
                    "end_date": parameters.end_date.isoformat(),
                }
                
                if parameters.customer_ids:
                    filter_data["customer_id"] = parameters.customer_ids[0]  # For now, handle single customer
                
                if parameters.agent_ids:
                    filter_data["agent_id"] = parameters.agent_ids[0]
                
                # Get transaction summary
                summary_response = await client.post(
                    f"{self.transaction_service_url}/transactions/summary",
                    json=filter_data,
                    timeout=30.0
                )
                
                if summary_response.status_code == 200:
                    summary_data = summary_response.json()
                else:
                    summary_data = {}
                
                # Get transaction details
                history_response = await client.post(
                    f"{self.transaction_service_url}/transactions/history",
                    json=filter_data,
                    params={"limit": 1000},
                    timeout=30.0
                )
                
                if history_response.status_code == 200:
                    history_data = history_response.json()
                    transactions = history_data.get("transactions", [])
                else:
                    transactions = []
                
                # Generate charts if requested
                charts = []
                if parameters.include_charts and summary_data:
                    charts = await self._generate_transaction_charts(summary_data, transactions)
                
                return {
                    "summary_stats": summary_data,
                    "transaction_details": transactions,
                    "charts": charts,
                    "report_title": "Transaction Summary Report",
                    "start_date": parameters.start_date.strftime("%Y-%m-%d"),
                    "end_date": parameters.end_date.strftime("%Y-%m-%d"),
                }
                
        except Exception as e:
            logger.error(f"Failed to collect transaction summary data: {e}")
            return {
                "summary_stats": {},
                "transaction_details": [],
                "charts": [],
                "error": str(e)
            }
    
    async def _collect_agent_performance_data(self, parameters: ReportParameters) -> Dict[str, Any]:
        """Collect agent performance data"""
        try:
            # This would integrate with your actual services
            # Return computed data structure
            agent_performance = [
                {
                    "agent_id": "AGT001",
                    "transaction_count": 150,
                    "total_amount": 75000.0,
                    "commission_earned": 750.0,
                    "average_amount": 500.0,
                    "success_rate": 0.95,
                },
                {
                    "agent_id": "AGT002",
                    "transaction_count": 120,
                    "total_amount": 60000.0,
                    "commission_earned": 600.0,
                    "average_amount": 500.0,
                    "success_rate": 0.92,
                },
            ]
            
            return {
                "agent_performance": agent_performance,
                "report_title": "Agent Performance Report",
                "start_date": parameters.start_date.strftime("%Y-%m-%d"),
                "end_date": parameters.end_date.strftime("%Y-%m-%d"),
            }
            
        except Exception as e:
            logger.error(f"Failed to collect agent performance data: {e}")
            return {"agent_performance": [], "error": str(e)}
    
    async def _collect_customer_analytics_data(self, parameters: ReportParameters) -> Dict[str, Any]:
        """Collect customer analytics data"""
        # Implementation would integrate with customer service
        return {"customer_analytics": [], "report_title": "Customer Analytics Report"}
    
    async def _collect_financial_overview_data(self, parameters: ReportParameters) -> Dict[str, Any]:
        """Collect financial overview data"""
        # Implementation would aggregate financial data
        return {"financial_overview": {}, "report_title": "Financial Overview Report"}
    
    async def _collect_fraud_analysis_data(self, parameters: ReportParameters) -> Dict[str, Any]:
        """Collect fraud analysis data"""
        # Implementation would integrate with fraud detection service
        return {"fraud_analysis": {}, "report_title": "Fraud Analysis Report"}
    
    async def _collect_compliance_data(self, parameters: ReportParameters) -> Dict[str, Any]:
        """Collect compliance data"""
        # Implementation would collect compliance-related data
        return {"compliance_data": {}, "report_title": "Compliance Report"}
    
    async def _collect_operational_metrics_data(self, parameters: ReportParameters) -> Dict[str, Any]:
        """Collect operational metrics data"""
        # Implementation would collect operational metrics
        return {"operational_metrics": {}, "report_title": "Operational Metrics Report"}
    
    async def _generate_transaction_charts(self, summary_data: Dict[str, Any], 
                                         transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate charts for transaction data"""
        charts = []
        
        try:
            # Transaction type distribution pie chart
            if "transaction_types" in summary_data:
                fig = px.pie(
                    values=list(summary_data["transaction_types"].values()),
                    names=list(summary_data["transaction_types"].keys()),
                    title="Transaction Types Distribution"
                )
                
                img_bytes = pio.to_image(fig, format="png", width=800, height=600)
                img_base64 = base64.b64encode(img_bytes).decode()
                
                charts.append({
                    "title": "Transaction Types Distribution",
                    "image": img_base64,
                    "type": "pie"
                })
            
            # Daily volume chart
            if "daily_volumes" in summary_data and summary_data["daily_volumes"]:
                daily_data = summary_data["daily_volumes"]
                dates = [item["date"] for item in daily_data]
                amounts = [item["amount"] for item in daily_data]
                
                fig = px.line(
                    x=dates,
                    y=amounts,
                    title="Daily Transaction Volume",
                    labels={"x": "Date", "y": "Amount ($)"}
                )
                
                img_bytes = pio.to_image(fig, format="png", width=800, height=600)
                img_base64 = base64.b64encode(img_bytes).decode()
                
                charts.append({
                    "title": "Daily Transaction Volume",
                    "image": img_base64,
                    "type": "line"
                })
            
            # Status distribution bar chart
            if "status_distribution" in summary_data:
                fig = px.bar(
                    x=list(summary_data["status_distribution"].keys()),
                    y=list(summary_data["status_distribution"].values()),
                    title="Transaction Status Distribution"
                )
                
                img_bytes = pio.to_image(fig, format="png", width=800, height=600)
                img_base64 = base64.b64encode(img_bytes).decode()
                
                charts.append({
                    "title": "Transaction Status Distribution",
                    "image": img_base64,
                    "type": "bar"
                })
                
        except Exception as e:
            logger.error(f"Failed to generate charts: {e}")
        
        return charts
    
    async def _generate_report_file(self, report_data: Dict[str, Any], 
                                  format: ReportFormat, execution_id: str) -> str:
        """Generate report file in specified format"""
        reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        filename = f"report_{execution_id}.{format.value}"
        file_path = os.path.join(reports_dir, filename)
        
        if format == ReportFormat.HTML:
            await self._generate_html_report(report_data, file_path)
        elif format == ReportFormat.PDF:
            await self._generate_pdf_report(report_data, file_path)
        elif format == ReportFormat.EXCEL:
            await self._generate_excel_report(report_data, file_path)
        elif format == ReportFormat.CSV:
            await self._generate_csv_report(report_data, file_path)
        elif format == ReportFormat.JSON:
            await self._generate_json_report(report_data, file_path)
        
        return file_path
    
    async def _generate_html_report(self, report_data: Dict[str, Any], file_path: str):
        """Generate HTML report"""
        try:
            report_type = report_data.get("report_type", "transaction_summary")
            template_name = f"{report_type}.html"
            
            try:
                template = self.jinja_env.get_template(template_name)
            except:
                # Fallback to transaction summary template
                template = self.jinja_env.get_template("transaction_summary.html")
            
            html_content = template.render(**report_data)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
        except Exception as e:
            logger.error(f"Failed to generate HTML report: {e}")
            raise
    
    async def _generate_pdf_report(self, report_data: Dict[str, Any], file_path: str):
        """Generate PDF report"""
        try:
            # First generate HTML, then convert to PDF
            html_path = file_path.replace('.pdf', '.html')
            await self._generate_html_report(report_data, html_path)
            
            # For now, just copy the HTML file
            # In production, you'd use a library like weasyprint or pdfkit
            import shutil
            shutil.copy(html_path, file_path.replace('.pdf', '_temp.html'))
            
            # Create a simple PDF using reportlab
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title = report_data.get("report_title", "Report")
            story.append(Paragraph(title, styles['Title']))
            story.append(Spacer(1, 12))
            
            # Summary stats
            if "summary_stats" in report_data and report_data["summary_stats"]:
                stats = report_data["summary_stats"]
                story.append(Paragraph("Summary Statistics", styles['Heading2']))
                
                summary_text = f"""
                Total Transactions: {stats.get('total_transactions', 0)}<br/>
                Total Amount: ${stats.get('total_amount', 0):,.2f}<br/>
                Average Amount: ${stats.get('average_amount', 0):,.2f}
                """
                story.append(Paragraph(summary_text, styles['Normal']))
                story.append(Spacer(1, 12))
            
            # Transaction details table
            if "transaction_details" in report_data and report_data["transaction_details"]:
                story.append(Paragraph("Transaction Details", styles['Heading2']))
                
                transactions = report_data["transaction_details"][:50]  # Limit for PDF
                table_data = [["Transaction ID", "Date", "Type", "Amount", "Status"]]
                
                for txn in transactions:
                    table_data.append([
                        txn.get("transaction_id", "")[:15],
                        txn.get("created_at", "")[:10],
                        txn.get("transaction_type", ""),
                        f"${txn.get('amount', 0):,.2f}",
                        txn.get("status", "")
                    ])
                
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(table)
            
            doc.build(story)
            
        except Exception as e:
            logger.error(f"Failed to generate PDF report: {e}")
            raise
    
    async def _generate_excel_report(self, report_data: Dict[str, Any], file_path: str):
        """Generate Excel report"""
        try:
            workbook = xlsxwriter.Workbook(file_path)
            
            # Summary worksheet
            summary_sheet = workbook.add_worksheet('Summary')
            
            # Formats
            title_format = workbook.add_format({
                'bold': True,
                'font_size': 16,
                'align': 'center'
            })
            
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D3D3D3',
                'border': 1
            })
            
            cell_format = workbook.add_format({'border': 1})
            
            # Title
            summary_sheet.merge_range('A1:E1', report_data.get("report_title", "Report"), title_format)
            
            # Summary stats
            if "summary_stats" in report_data and report_data["summary_stats"]:
                stats = report_data["summary_stats"]
                
                summary_sheet.write('A3', 'Summary Statistics', header_format)
                summary_sheet.write('A4', 'Total Transactions', cell_format)
                summary_sheet.write('B4', stats.get('total_transactions', 0), cell_format)
                summary_sheet.write('A5', 'Total Amount', cell_format)
                summary_sheet.write('B5', stats.get('total_amount', 0), cell_format)
                summary_sheet.write('A6', 'Average Amount', cell_format)
                summary_sheet.write('B6', stats.get('average_amount', 0), cell_format)
            
            # Transaction details worksheet
            if "transaction_details" in report_data and report_data["transaction_details"]:
                details_sheet = workbook.add_worksheet('Transactions')
                
                headers = ['Transaction ID', 'Date', 'Customer ID', 'Type', 'Amount', 'Status']
                for col, header in enumerate(headers):
                    details_sheet.write(0, col, header, header_format)
                
                transactions = report_data["transaction_details"]
                for row, txn in enumerate(transactions, 1):
                    details_sheet.write(row, 0, txn.get("transaction_id", ""), cell_format)
                    details_sheet.write(row, 1, txn.get("created_at", ""), cell_format)
                    details_sheet.write(row, 2, txn.get("customer_id", ""), cell_format)
                    details_sheet.write(row, 3, txn.get("transaction_type", ""), cell_format)
                    details_sheet.write(row, 4, txn.get("amount", 0), cell_format)
                    details_sheet.write(row, 5, txn.get("status", ""), cell_format)
            
            workbook.close()
            
        except Exception as e:
            logger.error(f"Failed to generate Excel report: {e}")
            raise
    
    async def _generate_csv_report(self, report_data: Dict[str, Any], file_path: str):
        """Generate CSV report"""
        try:
            if "transaction_details" in report_data and report_data["transaction_details"]:
                df = pd.DataFrame(report_data["transaction_details"])
                df.to_csv(file_path, index=False)
            else:
                # Create empty CSV with headers
                df = pd.DataFrame(columns=["transaction_id", "created_at", "customer_id", "type", "amount", "status"])
                df.to_csv(file_path, index=False)
                
        except Exception as e:
            logger.error(f"Failed to generate CSV report: {e}")
            raise
    
    async def _generate_json_report(self, report_data: Dict[str, Any], file_path: str):
        """Generate JSON report"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"Failed to generate JSON report: {e}")
            raise
    
    async def get_report_status(self, execution_id: str) -> Dict[str, Any]:
        """Get report generation status"""
        db = SessionLocal()
        try:
            execution = db.query(ReportExecution).filter(ReportExecution.id == execution_id).first()
            
            if not execution:
                raise HTTPException(status_code=404, detail="Report execution not found")
            
            return {
                "execution_id": execution.id,
                "report_name": execution.report_name,
                "status": execution.status,
                "format": execution.format,
                "file_size": execution.file_size,
                "execution_time": execution.execution_time,
                "error_message": execution.error_message,
                "created_at": execution.created_at.isoformat(),
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            }
            
        except Exception as e:
            logger.error(f"Failed to get report status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def download_report(self, execution_id: str) -> tuple[str, str]:
        """Get report file path and content type for download"""
        db = SessionLocal()
        try:
            execution = db.query(ReportExecution).filter(ReportExecution.id == execution_id).first()
            
            if not execution:
                raise HTTPException(status_code=404, detail="Report execution not found")
            
            if execution.status != ReportStatus.COMPLETED.value:
                raise HTTPException(status_code=400, detail="Report is not ready for download")
            
            if not execution.file_path or not os.path.exists(execution.file_path):
                raise HTTPException(status_code=404, detail="Report file not found")
            
            # Determine content type
            content_types = {
                "pdf": "application/pdf",
                "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "csv": "text/csv",
                "json": "application/json",
                "html": "text/html",
            }
            
            content_type = content_types.get(execution.format, "application/octet-stream")
            
            return execution.file_path, content_type
            
        except Exception as e:
            logger.error(f"Failed to prepare report download: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check endpoint"""
        db = SessionLocal()
        try:
            # Check database connection
            db.execute("SELECT 1")
            db_healthy = True
        except Exception:
            db_healthy = False
        finally:
            db.close()
        
        # Check Redis connection
        redis_healthy = False
        if self.redis_client:
            try:
                await self.redis_client.ping()
                redis_healthy = True
            except Exception:
                redis_healthy = False
        
        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "reporting-service",
            "version": "1.0.0",
            "components": {
                "database": db_healthy,
                "redis": redis_healthy,
            }
        }

# FastAPI application
app = FastAPI(title="Reporting Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instance
reporting_service = ReportingService()

# Pydantic models for API
class ReportParametersModel(BaseModel):
    start_date: datetime
    end_date: datetime
    customer_ids: Optional[List[str]] = None
    agent_ids: Optional[List[str]] = None
    transaction_types: Optional[List[str]] = None
    include_charts: bool = True
    include_summary: bool = True
    include_details: bool = True
    group_by: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None

class ReportRequestModel(BaseModel):
    report_type: ReportType
    parameters: ReportParametersModel
    format: ReportFormat
    requested_by: str

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    await reporting_service.initialize()

@app.post("/generate-report")
async def generate_report(request: ReportRequestModel):
    """Generate a report"""
    parameters = ReportParameters(**request.parameters.dict())
    execution_id = await reporting_service.generate_report(
        request.report_type, parameters, request.format, request.requested_by
    )
    return {"execution_id": execution_id, "status": "generating"}

@app.get("/reports/{execution_id}/status")
async def get_report_status(execution_id: str):
    """Get report generation status"""
    return await reporting_service.get_report_status(execution_id)

@app.get("/reports/{execution_id}/download")
async def download_report(execution_id: str):
    """Download generated report"""
    file_path, content_type = await reporting_service.download_report(execution_id)
    
    def iterfile():
        with open(file_path, mode="rb") as file_like:
            yield from file_like
    
    filename = os.path.basename(file_path)
    
    return StreamingResponse(
        iterfile(),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await reporting_service.health_check()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8013)
