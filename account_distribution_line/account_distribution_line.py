# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Addons modules by CLEARCORP S.A.
#    Copyright (C) 2009-TODAY CLEARCORP S.A. (<http://clearcorp.co.cr>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, orm

class accountDistributionline(orm.Model):
    _name = "account.distribution.line"
    _description = "Account Distribution Line"
    
    _columns = {         
         'account_move_line_id': fields.many2one('account.move.line', 'Account Move Line', ondelete="cascade"),
         'distribution_percentage': fields.float('Distribution Percentage', required=True, digits_compute=dp.get_precision('Account'),),
         'distribution_amount': fields.float('Distribution Amount', digits_compute=dp.get_precision('Account'), required=True),
         'target_account_move_line_id': fields.many2one('account.move.line', 'Target Budget Move Line'),
         'reconcile_ids': fields.many2many('account.move.reconcile','bud_reconcile_distribution_ids'),
         'type': fields.selection([('manual', 'Manual'),('auto', 'Automatic')], 'Distribution Type', select=True),
         'account_move_line_type': fields.selection([('liquid', 'Liquid'),('void', 'Void')], 'Budget Type', select=True),
    }
    
    #======== Check distribution percentage. Use distribution_percentage_sum in account.move.line to check 
    def _check_distribution_percentage(self, cr, uid, ids, context=None):          
        
        for distribution in self.browse(cr, uid, ids, context=context):
            #distribution_percentage_sum compute all the percentages for a specific move line. 
            line_percentage = distribution.account_move_line_id.distribution_percentage_sum or 0.0
            line_percentage_remaining = 100 - line_percentage
            
            if distribution.distribution_percentage > line_percentage_remaining:
                return False
            
            return True
        
    #========= Check distribution percentage. Use distribution_amount_sum in account.move.line to check 
    def _check_distribution_amount(self, cr, uid, ids, context=None):          
        amount = 0.0
        
        for distribution in self.browse(cr, uid, ids, context=context):
            #==== distribution_amount_sum compute all the percentages for a specific move line. 
            x = distribution.account_move_line_id
            y = distribution.account_move_line_id.id
            line_amount_dis = distribution.account_move_line_id.distribution_amount_sum or 0.0
            
            #=====Find amount for the move_line
            if distribution.account_move_line_id.credit > 0:
                amount = distribution.account_move_line_id.credit
            if distribution.account_move_line_id.debit > 0:
                amount = distribution.account_move_line_id.debit
            
            #Only in case of budget distribution
            if distribution.account_move_line_id.credit == 0 and distribution.account_move_line_id.debit == 0:
                if distribution.account_move_line_id.fixed_amount:
                    amount = distribution.account_move_line_id.fixed_amount
            
            #====Check which is the remaining between the amount line and sum of amount in distributions. 
            amount_remaining = amount - line_amount_dis
            
            if distribution.distribution_amount > amount_remaining:
                return False            
            
            return True