#!/usr/bin/env python3
"""Canonical 100k-row fixtures from frozen Census series distributed by FRED.

Synthetic shards partition each observed dollar amount; they never duplicate the
national totals or pretend to be observed firms. No Executive_Summary is created.
"""
import argparse
from collections import defaultdict
import csv
import gc
import hashlib
import io
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import office
from openpyxl import Workbook
from openpyxl.chart import LineChart, PieChart, Reference
from openpyxl.styles import Font, PatternFill
from office_trace_bench.contracts import read_json, sha256, write_json
from office_trace_bench.workbooks import workbook_snapshot
from office_trace_bench.prompts import render_prompt

RETAIL = {'MRTSSM441USS':'Motor vehicle and parts dealers', 'MRTSSM442USS':'Furniture and home furnishings',
          'MRTSSM443USS':'Electronics and appliance stores', 'MRTSSM445USS':'Food and beverage stores',
          'MRTSSM446USS':'Health and personal care stores', 'MRTSSM448USS':'Clothing and accessories stores'}
M3 = ['AMTMVS','AMTMNO','AMTMUO','AMTMTI']


def source_rows(dataset):
    if dataset == 'retail':
        source = ROOT / 'sources/xlsx/retail_fred.csv'
        rows = list(csv.DictReader(source.open()))
        seeds = []
        for row in rows:
            if '2023-01-01' <= row['observation_date'] <= '2024-12-31':
                for code,name in RETAIL.items():
                    seeds.append(dict(period=row['observation_date'][:7], category=code, name=name,
                                      amounts=[int(row[code])*1000000,0,0,0]))
        return source, seeds, list(RETAIL)
    source = ROOT / 'sources/xlsx/manufacturing_fred.zip'
    merged = {}
    with zipfile.ZipFile(source) as archive:
        for name in archive.namelist():
            if name.endswith('.csv'):
                for row in csv.DictReader(io.StringIO(archive.read(name).decode())):
                    if '2023-01-01' <= row['observation_date'] <= '2024-12-31':
                        merged.setdefault(row['observation_date'], {}).update(row)
    seeds = [dict(period=date[:7], category='TotalManufacturing', name='Total manufacturing',
                  amounts=[int(row[code])*1000000 for code in M3]) for date,row in sorted(merged.items())]
    return source, seeds, M3


def table(book, name, header, rows):
    sheet = book.create_sheet(name)
    sheet.append(header)
    for row in rows:sheet.append(row)
    for cell in sheet[1]:
        cell.font = Font(name='Arial', bold=True, color='FFFFFF')
        cell.fill = PatternFill(fill_type='solid', start_color='1F4E79', end_color='1F4E79')
    sheet.freeze_panes = 'A2'
    for col in 'ABCDEFG':sheet.column_dimensions[col].width = 22
    return sheet


def build(dataset, raw_count=100000):
    target = ROOT / 'datasets/xlsx' / dataset
    if (target / 'manifest.json').exists():raise ValueError('dataset exists; refusing to overwrite frozen inputs')
    folder = target / 'input';folder.mkdir(parents=True, exist_ok=True)
    source, seeds, series = source_rows(dataset)
    assert len({x['period'] for x in seeds}) == 24
    book = Workbook();raw = book.active;raw.title='Raw_Data'
    header=['RecordID','SourceRowID','Dataset','Period','CategoryCode','CategoryName','Segment',
            'SalesUSD' if dataset=='retail' else 'ShipmentsUSD','NewOrdersUSD','UnfilledOrdersUSD',
            'InventoriesUSD','SourcePrimaryUSD','ShardIndex','ShardCount','Origin','RowChecksum']
    raw.append(header)
    monthly=defaultdict(lambda:[0,0,0,0]);categories=defaultdict(int);segments=defaultdict(lambda:[0,0,0,0])
    seed_count=len(seeds)
    for index,seed in enumerate(seeds):
        repeats=raw_count//seed_count+(index<raw_count%seed_count)
        monthly[seed['period']]=[a+b for a,b in zip(monthly[seed['period']],seed['amounts'])]
        categories[seed['name']]+=seed['amounts'][0]
        for shard in range(repeats):
            amounts=[value//repeats+(shard<value%repeats) for value in seed['amounts']]
            segment='Benchmark segment '+str(shard%6+1)
            segments[segment]=[a+b for a,b in zip(segments[segment],amounts)]
            identifier=f'{dataset}-{index+1:04d}-{shard+1:05d}'
            row=[identifier,f'source-{index+1:04d}',dataset,seed['period'],seed['category'],seed['name'],segment,
                 *amounts,seed['amounts'][0],shard+1,repeats,'synthetic_partition',
                 hashlib.sha256(identifier.encode()).hexdigest()[:24]]
            raw.append(row)
    assert raw.max_row == raw_count+1 and raw.max_column == 16
    raw.freeze_panes='A2';raw.auto_filter.ref=raw.dimensions
    periods=sorted(monthly);last=periods[-1]
    if dataset=='retail':
        monthly_sheet=table(book,'Monthly_Summary',['Period','Selected-category sales USD'],[[p,monthly[p][0]] for p in periods])
        category_sheet=table(book,'Category_Summary',['Category','Two-year sales USD'],sorted(categories.items()))
        largest=max(categories,key=categories.get)
        category_sheet['D1']='Largest selected category';category_sheet['D2']=largest
        growth=table(book,'Growth_Summary',['Period','MoM Growth','YoY Growth'],
                     [[p,0,0] for p in periods])
        for row in range(2,26):
            if row>2:growth[f'B{row}']=f'=Monthly_Summary!B{row}/Monthly_Summary!B{row-1}-1'
            if row>=14:growth[f'C{row}']=f'=Monthly_Summary!B{row}/Monthly_Summary!B{row-12}-1'
        table(book,'Sales_Mix',['Category','Two-year sales USD'],sorted(categories.items()))
        table(book,'Source_Summary',['Period','Category','Published sales USD'],[[s['period'],s['name'],s['amounts'][0]] for s in seeds])
        values=[monthly[last][0],monthly[last][0]/monthly[periods[-2]][0]-1,
                monthly[last][0]/monthly[periods[-13]][0]-1,largest]
        refs=['Monthly_Summary!B25','Growth_Summary!B25','Growth_Summary!C25','Category_Summary!D2']
        labels=['Latest Month Selected-category Sales','Month-over-Month Growth','Year-over-Year Growth','Largest Selected Category']
        formats=['$#,##0','0.0%','0.0%',None]
        scenario_labels=['Sales price multiplier','Sales volume multiplier']
        projected=[('Projected Sales at Base Prices',['B5','B14']),('Projected Sales Revenue',['B5','B13','B14'])]
        chart_specs=[dict(id='monthly_sales',description='a monthly sales trend',required_references=['Monthly_Summary!']),
                     dict(id='category_mix',description='a selected-category sales mix',required_references=['Sales_Mix!'])]
        category_chart_sheet=book['Sales_Mix']
    else:
        monthly_sheet=table(book,'Shipment_Summary',['Period','Shipments USD'],[[p,monthly[p][0]] for p in periods])
        table(book,'Order_Summary',['Period','New orders USD','Unfilled orders USD'],[[p,monthly[p][1],monthly[p][2]] for p in periods])
        inventory=table(book,'Inventory_Summary',['Period','Unfilled orders USD','Inventories USD','Shipments USD','Inventory-to-shipments ratio'],
                        [[p,monthly[p][2],monthly[p][3],monthly[p][0],f'=C{i}/D{i}'] for i,p in enumerate(periods,2)])
        category_sheet=table(book,'Segment_Summary',['Synthetic benchmark segment','Shipments USD','New orders USD','Unfilled orders USD','Inventories USD'],
                             [[name,*amounts] for name,amounts in sorted(segments.items())])
        table(book,'Trend_Summary',['Period','Shipments USD','New orders USD','Inventories USD'],[[p,monthly[p][0],monthly[p][1],monthly[p][3]] for p in periods])
        values=[monthly[last][0],monthly[last][1],monthly[last][2],monthly[last][3]/monthly[last][0]]
        refs=['Shipment_Summary!B25','Order_Summary!B25','Order_Summary!C25','Inventory_Summary!E25']
        labels=['Latest Month Shipments','Latest Month New Orders','Latest Month Unfilled Orders','Inventory-to-Shipments Ratio']
        formats=['$#,##0','$#,##0','$#,##0','0.00"x"']
        scenario_labels=['Order value multiplier','Shipment volume multiplier']
        projected=[('Projected Shipments',['B5','B14']),('Projected New Orders',['B6','B13','B14'])]
        chart_specs=[dict(id='orders_shipments',description='an orders versus shipments trend',required_references=['Trend_Summary!']),
                     dict(id='inventory_trend',description='an inventory trend',required_references=['Inventory_Summary!'])]
        category_chart_sheet=category_sheet
    recon=table(book,'Reconciliation',['Check','Value'],[
        ['Raw primary total',f'=SUM(Raw_Data!H2:H{raw_count+1})'],['Summary primary total','=SUM('+monthly_sheet.title+'!B2:B25)'],
        ['Primary total agrees','=IF(B2=B3,"PASS","REVIEW")'],['Raw count',f'=COUNTA(Raw_Data!A2:A{raw_count+1})'],
        ['Expected raw count',raw_count],['Count agrees','=IF(B5=B6,"PASS","REVIEW")']])
    recon['A15']='Overall status';recon['B15']='=IF(AND(B4="PASS",B7="PASS"),"PASS","REVIEW")'
    line=LineChart();line.title='Existing primary trend';line.add_data(Reference(monthly_sheet,min_col=2,min_row=1,max_row=25),titles_from_data=True)
    line.set_categories(Reference(monthly_sheet,min_col=1,min_row=2,max_row=25));monthly_sheet.add_chart(line,'D2')
    pie=PieChart();pie.title='Existing category or benchmark segment mix';pie.add_data(Reference(category_chart_sheet,min_col=2,min_row=1,max_row=category_chart_sheet.max_row),titles_from_data=True)
    pie.set_categories(Reference(category_chart_sheet,min_col=1,min_row=2,max_row=category_chart_sheet.max_row));category_chart_sheet.add_chart(pie,'H2')
    baseline=workbook_snapshot(book,['Raw_Data'])
    initial_formula_count=sum(len(x) for x in baseline['formulas'].values())
    workbook=folder/'monthly_operations_template.xlsx';book.save(workbook);book.close();del book;gc.collect()
    refs_csv=folder/'prepared_monthly_operations_summary.csv'
    with refs_csv.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['period','primary_usd','new_orders_usd','unfilled_orders_usd','inventories_usd'])
        writer.writerows([p,*monthly[p]] for p in periods)
    recon_csv=folder/'prepared_reconciliation_summary.csv'
    with recon_csv.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['raw_rows','source_rows','partition_totals_preserved']);writer.writerow([raw_count,seed_count,True])
    source_url='https://fred.stlouisfed.org/graph/fredgraph.csv?id='+','.join(series)+'&cosd=2023-01-01&coed=2024-12-31'
    provenance=dict(publisher='U.S. Census Bureau',distributor='Federal Reserve Bank of St. Louis (FRED)',
                    source_url=source_url, source_artifact=str(source.relative_to(ROOT)),source_sha256=sha256(source),
                    series=series,selected_periods=['2023-01','2024-12'],observed_seed_rows=seed_count,
                    benchmark_raw_rows=raw_count,raw_rows_are_observed_firms=False,
                    expansion='Integer-dollar partition: each observed amount split across deterministic synthetic shards; source totals preserved.',
                    units='USD converted from source millions of dollars',
                    dimensions='Published disjoint selected retail categories' if dataset=='retail' else 'National total; six explicitly synthetic benchmark segments, not industry estimates')
    write_json(folder/'template_manifest.json',dict(dataset_id=dataset,raw_count=raw_count,base_sheets=baseline['sheet_order'],
               existing_formula_count=initial_formula_count,existing_chart_count=2,source=provenance))
    (folder/'dataset_sources.md').write_text('# '+dataset+' benchmark inputs\n\n'+
        'Official publisher: U.S. Census Bureau; frozen data obtained from FRED.\nSource: '+source_url+'\n\n'+
        'Only January 2023–December 2024 observations are selected from the downloaded history.\n'+
        'Raw_Data contains 100,000 SYNTHETIC workload shards, not observed establishments or transactions.\n'+
        provenance['expansion']+' Each source million-dollar observation is converted to dollars.\n'+
        provenance['dimensions']+'. Never sum overlapping national/subsector totals.\n'+
        'Retail totals cover ONLY the six selected categories, not all U.S. retail. Manufacturing stock measures are shown for the latest month, not summed as annual flows.\n'+
        'Read template_manifest.json for provenance and dataset_manifest.json for required KPI references and scenario assumptions.\n'+
        'Preserve all existing sheets, raw rows, formulas, source values and both existing charts.\n')
    scenarios=[('Base',1.,1.),('Upside',1.08,1.05),('Downside',.93,.95)]
    scenario=dict(selector_cell='B12',default='Base',
        table_columns={'D':'Scenario','E':scenario_labels[0],'F':scenario_labels[1]},
        rows=[dict(name=name,cells={f'D{i}':name,f'E{i}':price,f'F{i}':volume}) for i,(name,price,volume) in enumerate(scenarios,13)],
        formula_metrics=[dict(name='Selected '+scenario_labels[0],cell='B13',required_references=['B12'],meaning='Look up selected multiplier',font_color='000000'),
                         dict(name='Selected '+scenario_labels[1],cell='B14',required_references=['B12'],meaning='Look up selected multiplier',font_color='000000'),
                         *[dict(name=name,cell='B'+str(i),required_references=references,meaning='Multiply the referenced KPI by selected scenario multipliers',font_color='000000')
                           for i,(name,references) in enumerate(projected,15)]])
    cached={f'B{i}':value for i,value in enumerate(values,5)}
    cached.update(B9='PASS',B13=1,B14=1,B15=values[0],B16=values[0] if dataset=='retail' else values[1])
    write_json(target/'expected.json',dict(baseline=baseline,cached_values=cached,
        oracle_provenance='Independent Python aggregation of frozen official seed observations, before Agent edits; source partition conservation.'))
    metrics=[]
    for i,(label,ref,fmt) in enumerate(zip(labels,refs,formats),5):
        metric=dict(name=label,cell=f'B{i}',required_references=[ref],font_color='008000')
        if fmt:metric['number_format']=fmt
        metrics.append(metric)
    metrics.append(dict(name='Reconciliation Status',cell='B9',required_references=['Reconciliation!B15'],font_color='008000',
        prompt_instruction='cross-sheet formula returning PASS when Reconciliation!B15 is PASS, otherwise REVIEW.'))
    manifest=dict(schema_version='office-dataset-v1',kind='xlsx',dataset_id=dataset,domain=dataset,
        task='Enhance the existing '+dataset+' operations benchmark workbook',
        workbook=workbook.name,output_workbook='monthly_operations_report.xlsx',
        requirements=dict(summary_sheet='Executive_Summary',base_sheets=baseline['sheet_order'],raw_sheets=['Raw_Data'],
            minimum_bytes=1000000,minimum_formula_count=initial_formula_count+9,metrics=metrics,scenario=scenario,
            charts=chart_specs,minimum_conditional_formats=2,minimum_comments=2,recalc_timeout=180),
        publish_files=[dict(input=p.name,output=p.name.removeprefix('prepared_'),sha256=sha256(p)) for p in (refs_csv,recon_csv)],
        required_outputs=['monthly_operations_report.xlsx','monthly_operations_summary.csv','reconciliation_summary.csv',
                          'formula_recalc.json','business_verification.json','xlsx_enhancement_summary.json'],
        input_files={str(p.relative_to(target)):sha256(p) for p in sorted(folder.iterdir()) if p.is_file()},
        expected_file='expected.json',expected_sha256=sha256(target/'expected.json'),
        prompt_template='xlsx.txt',prompt_template_sha256=sha256(ROOT/'prompts/xlsx.txt'),
        prompt_contract=dict(task_subject='Census '+('MRTS retail' if dataset=='retail' else 'M3 manufacturing')+' January 2023–December 2024 benchmark workbook',
            raw_record_count=raw_count,original_chart_count=2,metadata_files=['template_manifest.json','dataset_sources.md']),
        runtime_case='SUB-MEM-OFFICE-'+dataset.upper()+'-01',
        agent_context=read_json(ROOT/'datasets/xlsx/tlc/manifest.json')['agent_context'],
        trace_rules=[dict(pattern=r'verify_office\.py',operation='verify_business'),dict(pattern=r'recalc\.py',operation='recalculate_formulas'),
                     dict(pattern=r'\bcp\b.*\.csv',operation='publish_csv'),dict(pattern='load_workbook',operation='inspect_workbook')],
        source_provenance=provenance)
    write_json(target/'manifest.json',manifest)
    render_prompt(manifest,'/validation/workspace',target/'manifest.json')
    print(dataset,raw_count,'rows;',len(baseline['sheet_order']),'sheets;',initial_formula_count,'existing formulas;',
          workbook.stat().st_size,'bytes',flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',choices=['retail','manufacturing'],required=True)
    args=parser.parse_args();build(args.dataset)
