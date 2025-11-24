"""
Export Service for generating CSV and PDF reports from analytics data.
"""
import csv
import io
from typing import Dict, List, Any
from datetime import datetime


class ExportService:
    
    @staticmethod
    def export_to_csv(data: Dict, filename: str = None) -> tuple:
        """
        Export data to CSV format.
        
        Args:
            data: Dictionary containing metrics data
            filename: Optional filename (default: metrics_YYYY-MM-DD.csv)
        
        Returns:
            Tuple of (csv_string, filename)
        """
        if filename is None:
            filename = f"metrics_{datetime.now().strftime('%Y-%m-%d')}.csv"
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Metric', 'Value'])
        
        # Flatten nested dictionaries
        def flatten_dict(d, parent_key='', sep='_'):
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(flatten_dict(v, new_key, sep=sep).items())
                elif isinstance(v, list):
                    # Handle lists (like daily_breakdown)
                    if v and isinstance(v[0], dict):
                        # Write list as separate section
                        writer.writerow([])
                        writer.writerow([new_key, ''])
                        if v:
                            # Write headers from first item
                            headers = list(v[0].keys())
                            writer.writerow(headers)
                            for item in v:
                                writer.writerow([item.get(h, '') for h in headers])
                    else:
                        items.append((new_key, ', '.join(str(x) for x in v)))
                else:
                    items.append((new_key, v))
            return dict(items)
        
        flattened = flatten_dict(data)
        for key, value in flattened.items():
            writer.writerow([key, value])
        
        csv_string = output.getvalue()
        output.close()
        
        return csv_string, filename
    
    @staticmethod
    def export_metrics_to_csv(metrics_type: str, data: Dict) -> tuple:
        """
        Export specific metrics type to CSV with proper formatting.
        
        Args:
            metrics_type: Type of metrics (engagement, appointments, revenue, etc.)
            data: Metrics data dictionary
        
        Returns:
            Tuple of (csv_string, filename)
        """
        filename = f"{metrics_type}_metrics_{datetime.now().strftime('%Y-%m-%d')}.csv"
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write title
        writer.writerow([f"{metrics_type.upper()} METRICS REPORT"])
        writer.writerow([f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
        writer.writerow([])
        
        # Write period if available
        if 'period' in data:
            period = data['period']
            writer.writerow(['Period'])
            writer.writerow(['Start Date', period.get('start_date', '')])
            writer.writerow(['End Date', period.get('end_date', '')])
            writer.writerow([])
        
        # Write summary metrics
        if 'summary' in data:
            writer.writerow(['SUMMARY'])
            summary = data['summary']
            for key, value in summary.items():
                writer.writerow([key.replace('_', ' ').title(), value])
            writer.writerow([])
        
        # Write daily breakdown if available
        if 'daily_breakdown' in data and data['daily_breakdown']:
            writer.writerow(['DAILY BREAKDOWN'])
            daily = data['daily_breakdown']
            if daily and isinstance(daily[0], dict):
                headers = list(daily[0].keys())
                writer.writerow(headers)
                for day in daily:
                    writer.writerow([day.get(h, '') for h in headers])
        
        # Write other sections
        for key, value in data.items():
            if key not in ['period', 'summary', 'daily_breakdown']:
                writer.writerow([])
                writer.writerow([key.replace('_', ' ').upper()])
                if isinstance(value, dict):
                    for k, v in value.items():
                        writer.writerow([k.replace('_', ' ').title(), v])
                elif isinstance(value, list):
                    if value and isinstance(value[0], dict):
                        headers = list(value[0].keys())
                        writer.writerow(headers)
                        for item in value:
                            writer.writerow([item.get(h, '') for h in headers])
        
        csv_string = output.getvalue()
        output.close()
        
        return csv_string, filename
    
    @staticmethod
    def export_to_pdf(data: Dict, metrics_type: str = "metrics") -> tuple:
        """
        Export data to PDF format.
        Note: Requires reportlab library. Falls back to CSV if not available.
        
        Args:
            data: Dictionary containing metrics data
            metrics_type: Type of metrics for filename
        
        Returns:
            Tuple of (pdf_bytes, filename)
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.lib import colors
        except ImportError:
            # Fallback to CSV if reportlab not available
            csv_string, csv_filename = ExportService.export_metrics_to_csv(metrics_type, data)
            return csv_string.encode('utf-8'), csv_filename.replace('.csv', '.txt')
        
        filename = f"{metrics_type}_metrics_{datetime.now().strftime('%Y-%m-%d')}.pdf"
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title = Paragraph(f"{metrics_type.upper()} METRICS REPORT", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 0.2*inch))
        
        # Date
        date_text = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
        story.append(date_text)
        story.append(Spacer(1, 0.3*inch))
        
        # Period
        if 'period' in data:
            period = data['period']
            period_text = f"Period: {period.get('start_date', '')} to {period.get('end_date', '')}"
            story.append(Paragraph(period_text, styles['Heading2']))
            story.append(Spacer(1, 0.2*inch))
        
        # Summary
        if 'summary' in data:
            story.append(Paragraph("SUMMARY", styles['Heading2']))
            summary = data['summary']
            summary_data = [[k.replace('_', ' ').title(), str(v)] for k, v in summary.items()]
            summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 0.3*inch))
        
        # Daily breakdown
        if 'daily_breakdown' in data and data['daily_breakdown']:
            story.append(Paragraph("DAILY BREAKDOWN", styles['Heading2']))
            daily = data['daily_breakdown']
            if daily and isinstance(daily[0], dict):
                headers = [h.replace('_', ' ').title() for h in daily[0].keys()]
                table_data = [headers]
                for day in daily[:30]:  # Limit to 30 days for PDF
                    table_data.append([str(day.get(h.lower().replace(' ', '_'), '')) for h in headers])
                
                daily_table = Table(table_data, repeatRows=1)
                daily_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 8)
                ]))
                story.append(daily_table)
                story.append(Spacer(1, 0.3*inch))
        
        # Build PDF
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes, filename

