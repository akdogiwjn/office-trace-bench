"""Frozen deterministic fictional record generators. No randomness or live PII."""


def w4():
    records = []
    for i in range(1, 11):
        status = ('single', 'married', 'head_of_household')[(i - 1) % 3]
        records.append(dict(id=f'employee_{i:02d}', first_name=f'Training{i:02d}', last_name='Example', address=f'{100 + i} Example Lane', city_state_zip='Example City, CA 90001', filing_flags={name: name == status for name in ('single', 'married', 'head_of_household')}, multiple_jobs=i % 2 == 0, children_credit='0', other_dependents_credit='0', total_credit='0', other_income=str(i * 100), deductions='0', extra_withholding=str(i * 5)))
    return {'employees': records, 'provenance': 'Deterministic fictional performance fixtures; amounts are supplied input values, not tax advice or computed eligibility.'}

def sba():
    records = []
    for number in range(1, 11):
        name = f'Example Training Business {number:02d} LLC'
        records.append(dict(id=f'applicant_{number:02d}', business_name=name, operating_name=name, trade_name=f'Training {number:02d}', industry_code='541511', phone=f'202-555-{100 + number:04d}', operation_year=str(2010 + number), business_address=f'{100 + number} Example Lane, Example City, CA 90001', project_address=f'{100 + number} Example Lane, Example City, CA 90001', contact_name=f'Training Owner {number:02d}', contact_email=f'training{number:02d}@example.invalid', existing_employees=str(10 + number), retained_jobs=str(5 + number), new_jobs=str(number), owner_name=f'Training Owner {number:02d}', owner_title='Training Manager', owner_percentage='100', owner_address='1 Example Lane, Example City, CA 90001', working_capital_amount=str(10000 + number * 1000), flags={field_id: field_id in ('OC', 'llc', 'working capital') for field_id in ['OC', 'EPC', 'soleprop', 'partnership', 'ccorp', 'scorp', 'llc', 'etother', 'working capital']}, answers={str(n) + answer: answer == 'no' for n in range(1, 14) for answer in ('yes', 'no')}))
    return dict(applicants=records, provenance='Fictional unsubmitted performance fixtures; supplied answers do not assert real borrower eligibility.')
