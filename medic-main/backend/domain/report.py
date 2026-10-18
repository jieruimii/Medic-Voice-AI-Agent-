"""A readable draft assembled only from sourced facts; no generated conclusions."""
def clinician_draft(snapshot):
    e=snapshot['encounter']
    lines=['MEDIC — ENCOUNTER REVIEW DRAFT',f"Encounter: {e['id']}",
           f"Status: {e['encounter_status'].replace('_',' ').upper()}",
           'Prototype documentation support — clinician review required.',
           '', 'STRUCTURED ENCOUNTER']
    for key,fact in e['facts'].items():
        value = 'explicitly unspecified' if fact['explicitly_unknown'] else fact['value']
        if value is None:
            value = fact['status']
        lines.extend([f"{key}: {value} [{fact['status']}]",f"  Source (medic): {fact['evidence']}"])
        for prior in fact['history']:
            lines.append(f"  History: {prior.get('value')} [{prior['status']}] — {prior.get('evidence','')}")
    lines.extend(['','DOCUMENTATION ISSUES'])
    for issue in snapshot['issues']:
        lines.append(f"{issue['rule']} · {issue['severity']}: {issue['reason']}")
    if not snapshot['issues']:
        lines.append('No unresolved prototype documentation issues.')
    lines.extend(['','SOURCE NARRATIVE',e['raw_narrative'],'','FOLLOW-UP SOURCE STATEMENTS'])
    narrative = e['raw_narrative']
    for turn in snapshot['turns']:
        if turn['text'] not in narrative:
            lines.append(turn['text'])
    lines.extend(['','This draft records medic-supplied information and limited NEMSIS-inspired validation.',
                  'It does not establish legal compliance, reimbursement, certification, or clinical correctness.'])
    return '\n'.join(lines)
