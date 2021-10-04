""" Specification of IBM Q Manhattan """
#***************************************************************************************************
# Copyright 2015, 2019 National Technology & Engineering Solutions of Sandia, LLC (NTESS).
# Under the terms of Contract DE-NA0003525 with NTESS, the U.S. Government retains certain rights
# in this software.
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License.  You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0 or in the LICENSE file in the root pyGSTi directory.
#***************************************************************************************************

qubits = ['Q' + str(x) for x in range(65)]

two_qubit_gate = 'Gcnot'

edgelist = [('Q0', 'Q1'), ('Q0', 'Q10'), ('Q1', 'Q0'), ('Q1', 'Q2'), ('Q2', 'Q1'), ('Q2', 'Q3'), ('Q3', 'Q2'),
            ('Q3', 'Q4'), ('Q4', 'Q3'), ('Q4', 'Q5'), ('Q4', 'Q11'), ('Q5', 'Q4'), ('Q5', 'Q6'), ('Q6', 'Q5'),
            ('Q6', 'Q7'), ('Q7', 'Q6'), ('Q7', 'Q8'), ('Q8', 'Q7'), ('Q8', 'Q9'), ('Q8', 'Q12'), ('Q9', 'Q8'),
            ('Q10', 'Q0'), ('Q10', 'Q13'), ('Q11', 'Q4'), ('Q11', 'Q17'), ('Q12', 'Q8'), ('Q12', 'Q21'), ('Q13', 'Q10'),
            ('Q13', 'Q14'), ('Q14', 'Q13'), ('Q14', 'Q15'), ('Q15', 'Q14'), ('Q15', 'Q16'), ('Q15', 'Q24'),
            ('Q16', 'Q15'), ('Q16', 'Q17'), ('Q17', 'Q11'), ('Q17', 'Q16'), ('Q17', 'Q18'), ('Q18', 'Q17'),
            ('Q18', 'Q19'), ('Q19', 'Q18'), ('Q19', 'Q20'), ('Q19', 'Q25'), ('Q20', 'Q19'), ('Q20', 'Q21'),
            ('Q21', 'Q12'), ('Q21', 'Q20'), ('Q21', 'Q22'), ('Q22', 'Q21'), ('Q22', 'Q23'), ('Q23', 'Q22'),
            ('Q23', 'Q26'), ('Q24', 'Q15'), ('Q24', 'Q29'), ('Q25', 'Q19'), ('Q25', 'Q33'), ('Q26', 'Q23'),
            ('Q26', 'Q37'), ('Q27', 'Q28'), ('Q27', 'Q38'), ('Q28', 'Q27'), ('Q28', 'Q29'), ('Q29', 'Q24'),
            ('Q29', 'Q28'), ('Q29', 'Q30'), ('Q30', 'Q29'), ('Q30', 'Q31'), ('Q31', 'Q30'), ('Q31', 'Q32'),
            ('Q31', 'Q39'), ('Q32', 'Q31'), ('Q32', 'Q33'), ('Q33', 'Q25'), ('Q33', 'Q32'), ('Q33', 'Q34'),
            ('Q34', 'Q33'), ('Q34', 'Q35'), ('Q35', 'Q34'), ('Q35', 'Q36'), ('Q35', 'Q40'), ('Q36', 'Q35'),
            ('Q36', 'Q37'), ('Q37', 'Q26'), ('Q37', 'Q36'), ('Q38', 'Q27'), ('Q38', 'Q41'), ('Q39', 'Q31'),
            ('Q39', 'Q45'), ('Q40', 'Q35'), ('Q40', 'Q49'), ('Q41', 'Q38'), ('Q41', 'Q42'), ('Q42', 'Q41'),
            ('Q42', 'Q43'), ('Q43', 'Q42'), ('Q43', 'Q44'), ('Q43', 'Q52'), ('Q44', 'Q43'), ('Q44', 'Q45'),
            ('Q45', 'Q39'), ('Q45', 'Q44'), ('Q45', 'Q46'), ('Q46', 'Q45'), ('Q46', 'Q47'), ('Q47', 'Q46'),
            ('Q47', 'Q48'), ('Q47', 'Q53'), ('Q48', 'Q47'), ('Q48', 'Q49'), ('Q49', 'Q40'), ('Q49', 'Q48'),
            ('Q49', 'Q50'), ('Q50', 'Q49'), ('Q50', 'Q51'), ('Q51', 'Q50'), ('Q51', 'Q54'), ('Q52', 'Q43'),
            ('Q52', 'Q56'), ('Q53', 'Q47'), ('Q53', 'Q60'), ('Q54', 'Q51'), ('Q54', 'Q64'), ('Q55', 'Q56'),
            ('Q56', 'Q52'), ('Q56', 'Q55'), ('Q56', 'Q57'), ('Q57', 'Q56'), ('Q57', 'Q58'), ('Q58', 'Q57'),
            ('Q58', 'Q59'), ('Q59', 'Q58'), ('Q59', 'Q60'), ('Q60', 'Q53'), ('Q60', 'Q59'), ('Q60', 'Q61'),
            ('Q61', 'Q60'), ('Q61', 'Q62'), ('Q62', 'Q61'), ('Q62', 'Q63'), ('Q63', 'Q62'), ('Q63', 'Q64'),
            ('Q64', 'Q54'), ('Q64', 'Q63')]

spec_format = 'ibmq_v2019'
