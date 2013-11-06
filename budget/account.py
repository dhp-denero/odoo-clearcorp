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
from osv import fields, osv
from openerp import netsvc
import decimal_precision as dp
from tools.translate import _
from datetime import datetime
from copy import copy

class AccountMoveReconcile(osv.Model):
    _inherit = 'account.move.reconcile'
    
    def unlink(self, cr, uid, ids, context={}):
        dist_obj = self.pool.get('account.move.line.distribution')
        bud_mov_obj = self.pool.get('budget.move')
        wf_service = netsvc.LocalService("workflow")
        dist_ids = dist_obj.search(cr, uid, [('reconcile_ids.id','in',ids)], context=context)
        dists = dist_obj.browse(cr, uid, dist_ids, context=context)
        budget_move_ids = []
        for dist in dists:
            if dist.target_budget_move_line_id and \
                dist.target_budget_move_line_id.budget_move_id and \
                dist.target_budget_move_line_id.budget_move_id.id not in budget_move_ids:
                budget_move_ids.append(dist.target_budget_move_line_id.budget_move_id.id)
        dist_obj.unlink(cr, uid, dist_ids, context=context)
        
        if budget_move_ids:
            bud_mov_obj.recalculate_values(cr, uid, budget_move_ids, context=context)
            for mov_id in budget_move_ids:
                bud_mov_obj._workflow_signal(cr, uid, [mov_id], 'button_check_execution', context=context)
        return super(AccountMoveReconcile, self).unlink(cr, uid, ids, context=context)
    
    def create(self, cr, uid, vals, context=None):
        reconcile_id = super(AccountMoveReconcile, self).create(cr, uid, vals, context=context)
        self.reconcile_budget_check(cr, uid, [reconcile_id], context=context)
        return reconcile_id
    
    def split_debit_credit(self,cr, uid, move_line_ids,context=None):
        #takes a list of given account move lines and classifies them in credit or debit
        #returns a dictionary with two keys('debit' and 'credit') and for values lists of account move line ids
        result ={}
        credit = []
        debit = []
        acc_move_line = self.pool.get('account.move.line')
        for line in acc_move_line.browse(cr, uid, move_line_ids,context=context):
            if line.credit > 0:
                credit.append(line.id)
            elif line.debit > 0:
                debit.append(line.id)
            elif line.debit == 0 and line.credit == 0:
                if line.amount_currency > 0:
                    debit.append(line.id)
                else:
                    credit.append(line.id)
        result ['debit'] = debit
        result ['credit'] = credit
        return result
    
    def split_move_noncash(self,cr, uid, move_ids,context=None):
        #Classifies every move line of the account move in cash or non cash
        #for a move, returns a dictionary, with the id of the move line as the key and 'cash' or 'non_cash' for values
        result ={}
#        acc_move_line = self.pool.get('account.move.line')
        acc_move_obj = self.pool.get('account.move')
        
        for move in acc_move_obj.browse(cr, uid, move_ids, context=context):
            cash = False
            for line in move.line_id:
                if line.account_id.moves_cash:
                    cash = True
            if cash:    
                result[move.id] = 'cash'
            else:
                result[move.id] = 'non_cash'
        return result
    
    def move_in_voucher(self,cr, uid, move_ids, context=None):
        #Checks if a move is in a voucher, returns the id of the voucher or -1 in case that is not in any
        acc_move_obj = self.pool.get('account.move')
        acc_vouch_obj = self.pool.get('account.voucher')
        for move_id in move_ids:
            voucher_search = acc_vouch_obj.search(cr, uid, [('move_id','=',move_id)], context=context)
            if len(voucher_search) > 0:
                return voucher_search[0]
            else:
                return -1
    
    def move_in_invoice(self,cr, uid, move_ids, context=None):
        #checks if a move is in an invoice, returns the id of the invoice or -1 in case that is not in any
        acc_move_obj = self.pool.get('account.move')
        acc_inv_obj = self.pool.get('account.invoice')
        for move_id in move_ids:
            invoice_search = acc_inv_obj.search(cr, uid, [('move_id','=',move_id)], context=context)
            if len(invoice_search) > 0:
                return invoice_search[0]
            else:
                return -1
    
    def line_in_move(self,cr, uid, line_ids, context=None):
        #checks if a move is in an invoice, returns the id of the invoice or -1 in case that is not in any
        mov_line_obj = self.pool.get('account.move.line')
        for line in mov_line_obj.browse(cr, uid, line_ids, context=context):
            return line.move_id.id
        return -1
    
    def create_budget_account_reconcile(self, cr, uid, invoice_id, payment_move_line_id, payment_reconcile_id, reconcile_ids, context=None):
        acc_inv_obj = self.pool.get('account.invoice')
        acc_vouch_obj = self.pool.get('account.voucher')
        move_line_obj = self.pool.get('account.move.line')
        amld = self.pool.get('account.move.line.distribution')
        bud_move_obj = self.pool.get('budget.move')
        bud_move_line_obj = self.pool.get('budget.move.line')
        
        currency_id = None
        amount = 0
        for line in move_line_obj.browse(cr, uid, [payment_move_line_id],context=context):
            if line.credit > 0:
                amount = line.credit
            elif line.debit > 0:
                amount = line.debit
            elif line.debit == 0 and line.credit == 0:
                amount = line.amount_currency
                currency_id = line.currency_id
        if currency_id:
            print 'TODO'
            #amount = how to get the equivalent in system currency?         
        invoice = acc_inv_obj.browse(cr, uid,[invoice_id],context = context)[0]
        
        bud_move = invoice.budget_move_id
        i=0
        sum = 0
        for line in bud_move.move_lines:
 #           amld.clean_reconcile_entries(cr, uid, [payment_move_line_id], context=None)
            if i < len(bud_move.move_lines)-1:
                perc = line.fixed_amount/bud_move.fixed_amount or 0
                amld.create(cr, uid, {'budget_move_id': bud_move.id,
                                         'budget_move_line_id': line.id,
                                         'account_move_line_id': payment_move_line_id,
                                         'account_move_reconcile_id': payment_reconcile_id,
                                         'amount' : amount * perc
                                         })
                sum += amount * perc
                i+=1
                
            amld.create(cr, uid, {'budget_move_id': bud_move.id,
                                         'budget_move_line_id': bud_move.move_lines[i].id,
                                         'account_move_line_id': payment_move_line_id,
                                         'account_move_reconcile_id': payment_reconcile_id,
                                         'amount' : amount - sum
                                         })
            bud_move_line_obj.write(cr, uid, [line.id],{'date': line.date}, context=context)
        bud_move_obj.write(cr, uid , [bud_move.id], {'code': bud_move.code}, context=context)
        
    
    def _get_move_counterparts(self, cr, uid, line, context={}):
        is_debit = True if line.debit else False
        res = []
        for move_line in line.move_id.line_id:
            if (is_debit and move_line.credit) or (not is_debit and move_line.debit):
                res.append(move_line)
        return res
    
    def _get_reconcile_counterparts(self, cr, uid, line, context={}):
        is_debit = True if line.debit else False
        reconcile_ids = []
        
        if line.reconcile_id:
            reconcile_lines = line.reconcile_id.line_id if line.reconcile_id and line.reconcile_id.line_id else []
            reconcile_ids.append(line.reconcile_id.id)
        elif line.reconcile_partial_id:
            reconcile_lines = line.reconcile_partial_id.line_partial_ids if line.reconcile_partial_id and line.reconcile_partial_id.line_partial_ids else []
            reconcile_ids.append(line.reconcile_partial_id.id)
        else:
            reconcile_lines = []
        
        res = []
        if reconcile_lines:
            for move_line in reconcile_lines:
                if (is_debit and move_line.credit) or (not is_debit and move_line.debit):
                    res.append(move_line)
        return reconcile_ids, res
    
    def _adjust_distributed_values(self, cr, uid, dist_ids, amount, context = {}):
        dist_obj = self.pool.get('account.move.line.distribution')
        distributed_amount = 0.0
        dists = dist_obj.browse(cr, uid, dist_ids, context = context)
        
        if amount <= 0.0:
            dist_obj.unlink(cr, uid, dist_ids, context = context)
            return True
        
        for dist in dists:
            distributed_amount += dist.distribution_amount
        if distributed_amount and distributed_amount > amount:
            for dist in dists:
                vals = {
                    'distribution_percentage':dist.distribution_percentage * amount / distributed_amount,
                    'distribution_amount':dist.distribution_amount * amount / distributed_amount,
                }
                dist_obj.write(cr, uid, [dist.id], vals, context = context)
            return True
        return False
    
    def _recursive_liquid_get_auto_distribution(self, cr, uid, original_line, actual_line = None, checked_lines = [], amount_to_dist = 0.0, original_amount_to_dist = 0.0, reconcile_ids = [], continue_reconcile = False, context={}):
        """
        Receives an account.move.line that moves liquid and was found creating a reconcile.
        This method starts at this line and "travels" through the moves and reconciles line counterparts
        to try to find a budget move to match with.
        Returns the list of account.move.line.distribution created, or an empty list.
        """
        
        dist_obj = self.pool.get('account.move.line.distribution')
        
        # Check if not first call and void type line. This kind of lines only can be navigated when called first by the main method.
        if actual_line and actual_line.move_id.budget_type == 'void':
            return []
        
        # Check if first call and not liquid or void line
        if not actual_line and not original_line.account_id.moves_cash:
            return []
        
        # Check for first call
        if not actual_line:
            dist_search = dist_obj.search(cr, uid, [('account_move_line_id','=',original_line.id)],context=context)
            dist_obj.unlink(cr,uid,dist_search,context=context)
            actual_line = original_line
            amount_to_dist = original_line.debit + original_line.credit
            original_amount_to_dist = amount_to_dist
            checked_lines = [actual_line.id]
        
        if not amount_to_dist:
            return []
        
        budget_lines = {}
        liquid_lines = {}
        none_lines = {}
        
        budget_amounts = {}
        liquid_amounts = {}
        
        budget_total = 0.0
        liquid_total = 0.0
        none_total = 0.0
        
        amount_total = 0.0
        
        new_reconcile_ids = copy(reconcile_ids)
        # Get line counterparts, if the reconcile flag is on, the counterparts are looked in the reconcile, if not move is used
        if continue_reconcile:
            line_reconcile_ids, counterparts = self._get_reconcile_counterparts(cr, uid, actual_line, context=context)
            new_reconcile_ids += line_reconcile_ids
        else:
            counterparts = self._get_move_counterparts(cr, uid, actual_line, context=context)
        
        for counterpart in counterparts:
            if counterpart.id not in checked_lines:
                if counterpart.move_id.budget_type == 'budget':
                    budget_lines[counterpart.id] = counterpart
                    budget_amounts[counterpart.id] = counterpart.debit + counterpart.credit
                    budget_total += counterpart.debit + counterpart.credit
                    amount_total += counterpart.debit + counterpart.credit
                elif counterpart.account_id.moves_cash:
                    liquid_lines[counterpart.id] = counterpart
                    liquid_amounts[counterpart.id] = counterpart.debit + counterpart.credit
                    liquid_total += counterpart.debit + counterpart.credit
                    amount_total += counterpart.debit + counterpart.credit
                else:
                    none_lines[counterpart.id] = counterpart
                    none_total += counterpart.debit + counterpart.credit
                    amount_total += counterpart.debit + counterpart.credit
            checked_lines.append(counterpart.id)
        
        if not (budget_lines or liquid_lines or none_lines):
            return []
        
        if amount_total and amount_total > amount_to_dist:
            budget_amount_to_dist = budget_total * amount_to_dist / amount_total
            liquid_amount_to_dist = liquid_total * amount_to_dist / amount_total
            none_amount_to_dist = amount_to_dist - budget_amount_to_dist - liquid_amount_to_dist
        elif amount_total:
            budget_amount_to_dist = budget_total
            liquid_amount_to_dist = liquid_total
            none_amount_to_dist = none_total
        else:
            # Nothing to distribute
            return []
        
        none_res = []
        if none_total:
            for line in none_lines.values():
                line_amount_to_dist = (none_amount_to_dist if line.debit + line.credit >= none_amount_to_dist else line.debit + line.credit)
                # Use none_amount_to_dist with all lines as we don't know which ones will find something
                none_res += self._recursive_liquid_get_auto_distribution(cr, uid, original_line,
                                                                 actual_line = line,
                                                                 checked_lines = checked_lines,
                                                                 amount_to_dist = line_amount_to_dist,
                                                                 original_amount_to_dist = original_amount_to_dist,
                                                                 reconcile_ids = new_reconcile_ids,
                                                                 continue_reconcile = (not continue_reconcile),
                                                                 context = context)
        
        # Check if there is budget, void or liquid lines, if not return none_res, even if its empty.
        budget_res = []
        liquid_res = []
        budget_distributed = 0.0
        liquid_distributed = 0.0
        bud_move_obj = self.pool.get('budget.move')
        if budget_lines or liquid_lines:
            # Write dists and build lists
            
            #dist_obj = self.pool.get('account.move.line.distribution')
            
            # Budget list
            budget_total = 0.0
            budget_budget_move_line_ids = []
            budget_budget_move_lines = []
            for line in budget_lines.values():
                budget_budget_move_lines += (line.move_id.budget_move_line_ids if line.move_id.budget_move_line_ids else [])
            for line in budget_budget_move_lines:
                budget_budget_move_line_ids.append(line.id)
                budget_total += line.compromised
            for line in budget_budget_move_lines:
                distribution_amount = line.compromised
                # If the resulting total of budget plus liquid lines is more than available, the amount has to be fractioned.
                if budget_total + liquid_amount_to_dist > amount_to_dist:
                    distribution_amount = distribution_amount * amount_to_dist / budget_total + liquid_amount_to_dist
                budget_distributed += distribution_amount
                vals = {
                    'account_move_line_id':         original_line.id,
                    'distribution_amount':          distribution_amount,
                    'distribution_percentage':      100 * distribution_amount / original_amount_to_dist,
                    'target_budget_move_line_id':   line.id,
                    'reconcile_ids':                [(6, 0, new_reconcile_ids)],
                    'type':                         'auto',
                    'account_move_line_type':       'liquid',
                }
                budget_res.append(dist_obj.create(cr, uid, vals, context = context))
                bud_move_obj._workflow_signal(cr, uid, [line.budget_move_id.id], 'button_check_execution', context=context)
                
            
            # Liquid list
            for line in liquid_lines.values():
                distribution_amount = liquid_amounts[line.id]
                liquid_distributed += distribution_amount
                vals = {
                    'account_move_line_id':         original_line.id,
                    'distribution_amount':          distribution_amount,
                    'distribution_percentage':      100 * distribution_amount / original_amount_to_dist,
                    'target_account_move_line_id':  line.id,
                    'reconcile_ids':                [(6, 0, new_reconcile_ids)],
                    'type':                         'auto',
                }
                liquid_res.append(dist_obj.create(cr, uid, vals, context = context))
                bud_move_obj._workflow_signal(cr, uid, [line.budget_move_id.id], 'button_check_execution', context=context)
            
        distributed_amount = budget_distributed + liquid_distributed
        
        # Check if some dists are returned to adjust their values
        if none_res:
            self._adjust_distributed_values(cr, uid, none_res, amount_to_dist - distributed_amount, context = context)
        
        return budget_res + liquid_res + none_res
    
    def _recursive_void_get_auto_distribution(self, cr, uid, original_line, actual_line = None, checked_lines = [], amount_to_dist = 0.0, original_amount_to_dist = 0.0, reconcile_ids = [], continue_reconcile = False, context={}):
        """
        Receives an account.move.line that is marked as void for budget moves and was found creating a reconcile.
        This method starts at this line and "travels" through the moves and reconciles line counterparts
        to try to find a budget move to match with.
        Returns the list of account.move.line.distribution created, or an empty list.
        """
        
        # Check if not first call and void type line. This kind of lines only can be navigated when called first by the main method.
        if actual_line and actual_line.move_id.budget_type == 'void':
            return []
        
        # Check if first call and not void line
        if not actual_line and not actual_line.move_id.budget_type == 'void':
            return []
        
        # Check for first call
        if not actual_line:
            actual_line = original_line
            amount_to_dist = original_line.debit + original_line.credit
            original_amount_to_dist = amount_to_dist
            checked_lines.append(actual_line.id)
        
        if not amount_to_dist:
            return []
        
        budget_lines = {}
        none_lines = {}
        
        budget_amounts = {}
        
        budget_total = 0.0
        none_total = 0.0
        
        amount_total = 0.0
        
        new_reconcile_ids = copy(reconcile_ids)
        # Get line counterparts, if the reconcile flag is on, the counterparts are looked in the reconcile, if not move is used
        if continue_reconcile:
            line_reconcile_ids, counterparts = self._get_reconcile_counterparts(cr, uid, actual_line, context=context)
            new_reconcile_ids += line_reconcile_ids
        else:
            counterparts = self._get_move_counterparts(cr, uid, actual_line, context=context)
        
        for counterpart in counterparts:
            if counterpart.id not in checked_lines:
                if counterpart.move_id.budget_type == 'budget':
                    budget_lines[counterpart.id] = counterpart
                    budget_amounts[counterpart.id] = counterpart.debit + counterpart.credit
                    budget_total += counterpart.debit + counterpart.credit
                    amount_total += counterpart.debit + counterpart.credit
                elif not counterpart.account_id.moves_cash and counterpart.move_id.budget_type != 'void':
                    none_lines[counterpart.id] = counterpart
                    none_total += counterpart.debit + counterpart.credit
                    amount_total += counterpart.debit + counterpart.credit
            checked_lines.append(counterpart.id)
        
        if not (budget_lines or none_lines):
            return []
        
        if amount_total and amount_total > amount_to_dist:
            budget_amount_to_dist = budget_total * amount_to_dist / amount_total
            none_amount_to_dist = amount_to_dist - budget_amount_to_dist
        elif amount_total:
            budget_amount_to_dist = budget_total
            none_amount_to_dist = none_total
        else:
            # Nothing to distribute
            return []
        
        none_res = []
        if none_total:
            for line in none_lines.values():
                line_amount_to_dist = (none_amount_to_dist if line.debit + line.credit >= none_amount_to_dist else line.debit + line.credit)
                # Use none_amount_to_dist with all lines as we don't know which ones will find something
                none_res += self._recursive_void_get_auto_distribution(cr, uid, original_line,
                                                                       actual_line = line,
                                                                       checked_lines = checked_lines,
                                                                       amount_to_dist = line_amount_to_dist,
                                                                       reconcile_ids = new_reconcile_ids,
                                                                       continue_reconcile = (not continue_reconcile),
                                                                       context = context)
        
        budget_res = []
        budget_distributed = 0.0
        # Check if there is budget, void or liquid lines, if not return none_res, even if its empty.
        if budget_lines:
            # Write dists and build lists
            
            dist_obj = self.pool.get('account.move.line.distribution')
            
            # Budget list
            budget_total = 0.0
            budget_budget_move_line_ids = []
            budget_budget_move_lines = []
            bud_move_obj = self.pool.get('budget.move')
            for line in budget_lines.values():
                budget_budget_move_lines += (line.move_id.budget_move_line_ids if line.move_id.budget_move_line_ids else [])
            for line in budget_budget_move_lines:
                budget_budget_move_line_ids.append(line.id)
                budget_total += line.compromised
            for line in budget_budget_move_lines:
                distribution_amount = line.compromised
                # If the resulting total of budget plus liquid lines is more than available, the amount has to be fractioned.
                if budget_total > amount_to_dist:
                    distribution_amount = distribution_amount * amount_to_dist / budget_total
                budget_distributed += distribution_amount
                vals = {
                    'account_move_line_id':         original_line.id,
                    'distribution_amount':          distribution_amount,
                    'distribution_percentage':      100 * distribution_amount / original_amount_to_dist,
                    'target_budget_move_line_id':   line.id,
                    'reconcile_ids':                [(6, 0, new_reconcile_ids)],
                    'type':                         'auto',
                    'account_move_line_type':       'liquid',
                }
                budget_res.append(dist_obj.create(cr, uid, vals, context = context))
                bud_move_obj._workflow_signal(cr, uid, [line.budget_move_id.id], 'button_check_execution', context=context)
        
        distributed_amount = budget_distributed
        
        # Check if some dists are returned to adjust their values
        if none_res:
            self._adjust_distributed_values(cr, uid, none_res, amount_to_dist - distributed_amount, context = context)
        
        return budget_res + none_res
    
    def _check_auto_distributions(self, cr, uid, line, dist_ids, context = {}):
        # Check for exact value computation
        if line and dist_ids:
            dist_obj = self.pool.get('account.move.line.distribution')
            dists = dist_obj.browse(cr, uid, dist_ids, context = context)
            distribution_amount = 0.0
            distribution_percentage = 0.0
            for dist in dists:
                distribution_amount += dist.distribution_amount
                distribution_percentage += dist.distribution_percentage
            last_dist = dists[-1]
            last_dist_distribution_amount = last_dist.distribution_amount
            last_dist_distribution_percentage = last_dist.distribution_percentage
            amount = line.debit + line.credit
            
            vals = {}
            if distribution_amount > amount:
                if (distribution_amount - amount) > last_dist_distribution_amount:
                    # Bad dists, the difference is bigger than the adjustment line (last line)
                    dist_obj.unlink(cr, uid, dist_ids, context=context)
                    return []
                else:
                    # Adjust difference
                    vals['distribution_amount'] = amount - (distribution_amount - last_dist_distribution_amount)
            elif distribution_amount < amount:
                vals['distribution_amount'] = amount - (distribution_amount - last_dist_distribution_amount)
            
            if 'distribution_amount' in vals:
                if last_dist.target_account_move_line_id and \
                    vals['distribution_amount'] > (last_dist.target_account_move_line_id.debit + last_dist.target_account_move_line_id.credit):
                    # New value is bigger than allowed value
                    dist_obj.unlink(cr, uid, dist_ids, context=context)
                    return []
                elif last_dist.target_budget_move_line_id and \
                    vals['distribution_amount'] > last_dist.target_budget_move_line_id.compromised:
                    # New value is bigger than allowed value
                    dist_obj.unlink(cr, uid, dist_ids, context=context)
                    return []
            
            if distribution_percentage > 100:
                if (distribution_percentage - 100) > last_dist_distribution_percentage:
                    # Bad dists, the difference is bigger than the adjustment line (last line)
                    dist_obj.unlink(cr, uid, dist_ids, context=context)
                    return []
                else:
                    # Adjust difference
                    vals['distribution_percentage'] = 100 - (distribution_percentage - last_dist_distribution_percentage)
            elif distribution_percentage < 100:
                vals['distribution_percentage'] = 100 - (distribution_percentage - last_dist_distribution_percentage)
            
            dist_obj.write(cr, uid, last_dist.id, vals, context=context)
            return dist_ids
    
    def reconcile_budget_check(self, cr, uid, ids, context={}):
        done_lines = []
        res = {}
        for reconcile in self.browse(cr, uid, ids, context=context):
            # Check if reconcile "touches" a move that touches a liquid account on any of its move lines
            
            # First get the moves of the reconciled lines
            if reconcile.line_id:
                moves = [line.move_id for line in reconcile.line_id]
            else:
                moves = [line.move_id for line in reconcile.line_partial_ids]
            # Then get all the lines of those moves, reconciled and counterparts
            move_lines = [line for move in moves for line in move.line_id]
            # Check if the account if marked as moves_cash
            for line in move_lines:
                if (line.id not in done_lines) and line.account_id and line.account_id.moves_cash:
                    dist_ids = self._recursive_liquid_get_auto_distribution(cr, uid, line, context=context)
                    checked_dist_ids = self._check_auto_distributions(cr, uid, line, dist_ids, context=context)
                    if checked_dist_ids:
                        res[line.id] = checked_dist_ids
                elif (line.id not in done_lines) and line.move_id.budget_type == 'void':
                    dist_ids = self._recursive_void_get_auto_distribution(cr, uid, line, context=context)
                    checked_dist_ids = self._check_auto_distributions(cr, uid, line, dist_ids, context=context)
                    if checked_dist_ids:
                        res[line.id] = checked_dist_ids
                done_lines.append(line.id)
            
            # Recalculate budget move values
            if res:
                budget_move_ids = []
                dist_obj = self.pool.get('account.move.line.distribution')
                dist_ids = [dist_id for dist_ids in res.values() for dist_id in dist_ids]
                dists = dist_obj.browse(cr, uid, dist_ids)
                for dist in dists:
                    if dist.target_budget_move_line_id and dist.target_budget_move_line_id.budget_move_id:
                        budget_move_ids.append(dist.target_budget_move_line_id.budget_move_id.id)
                if budget_move_ids:
                    budget_move_obj = self.pool.get('budget.move')
                    budget_move_obj.recalculate_values(cr, uid, budget_move_ids, context = context)
        return res
    
#     def on_create_budget_check(self, cr, uid, ids, visited_reconciles,trace_reconciled_ids, passing_through, context=None):
#         voucher_obj = self.pool.get('account.voucher')
#         acc_move_obj = self.pool.get('account.move')
#         voucher_present = False
#         invoice_present = False
#         
#         for reconcile in self.browse(cr, uid, ids, context=context):
#             local_trace_reconciled_ids = trace_reconciled_ids
#             local_trace_reconciled_ids.append(reconcile.id)
#             local_visited_reconciles = visited_reconciles
#             lines = []
#             line_ids = []
#             move_ids = []
#              
#             #choosing between partial or total reconcile
#             if reconcile.line_id:
#                 lines = reconcile.line_id
#             elif reconcile.line_partial_ids:
#                 lines = reconcile.line_partial_ids
#              
#             #getting move_line_ids from reconcile lines
#             reconcile_line_ids =  map(lambda x: x.id, lines)
#             #getting move_ids from reconcile lines
#             move_ids = map(lambda x: x.move_id.id, lines)
#              
#              
#             cash_moves = self.split_move_noncash(cr, uid, move_ids, context=context)
#              
#             if 'cash' in cash_moves.values():
#                 for move in acc_move_obj.browse( cr, uid, move_ids, context=context):
#                     if cash_moves[move.id] == 'cash':                                      #if it moves cash and
#                         voucher_id = self.move_in_voucher(cr, uid, [move.id], context=context)
#                         #if voucher_id != -1:                                               #is a voucher
#                         classified_reconciled_lines = self.split_debit_credit(cr, uid, reconcile_line_ids, context)
#                         for line in move.line_id:
#                             reconcile_id = line.reconcile_id or line.reconcile_partial_id
#                             if line.id in reconcile_line_ids:
#                                 reconcile_counterpart_ids = self.get_counterparts(cr, uid, line.id, classified_reconciled_lines, context)
#                                 for counter_id in reconcile_counterpart_ids:
#                                      move_counter_id = self.line_in_move(cr, uid, [counter_id], context)
#                                      invoice_id = self.move_in_invoice(cr, uid, [move_counter_id], context=context)
#                                      if invoice_id != -1:
#                                          self.create_budget_account_reconcile(cr, uid, invoice_id, line.id, reconcile_id.id, local_trace_reconciled_ids, context=context)
#                                      else:
#                                         print ("else if no t in invoice")
#                                            
#                           
#             elif passing_through:
#                 print ("TODO PASS THROUGH")

class AccountMoveLine(osv.Model):
    _inherit = 'account.move.line'
    
    _columns = {
        'distribution_ids' : fields.one2many('account.move.line.distribution', 'account_move_line_id', 'Distributions'),
    }

class AccountMove(osv.Model):
    _inherit = 'account.move'
    
    OPTIONS = [
        ('void', 'Voids budget move'),
        ('budget', 'Budget move'),
    ]
    
    _columns = {
        'budget_move_line_ids':  fields.one2many('budget.move.line', 'account_move_id', 'Budget move lines'),
        'budget_type': fields.selection(OPTIONS, 'budget_type', readonly=True),
    }

class Account(osv.Model):
    _inherit = 'account.account'
    
    _columns = {
        'default_budget_program_line' : fields.many2one('budget.program.line','Default budget program line'),
    }