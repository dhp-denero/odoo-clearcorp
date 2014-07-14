# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Original Module by SIESA (<http://www.siesacr.com>)
#    Refactored by CLEARCORP S.A. (<http://clearcorp.co.cr>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    license, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
##############################################################################

from openerp.osv import osv, fields

class CommissionRule(osv.Model):
    """Commission Rule"""

    _name = 'sale.commission.rule'

    _description = __doc__

    def _check_post_expiration_days(self, cr, uid, ids, context=None):
        for rule in self.browse(cr, uid, ids, context=context):
            if rule.post_expiration_days < 0:
                return False
        return True

    _columns = {
        'name': fields.char('Rule Name', size=128, required=True),
        'member_ids': fields.one2many('res.users','sale_commission_rule_id', string='Members'),
        'post_expiration_days': fields.integer(string='Post-Expiration Days', required=True),
        'line_ids': fields.one2many('sale.commission.rule.line', 'commission_rule_id', 'Rule Lines')
    }

    _constraints = [(_check_post_expiration_days,'Value must be greater or equal than 0.',
                     ['post_expiration_days'])]

class CommissionRuleLine(osv.Model):
    """Commission Rule Line"""

    _name = 'sale.commission.rule.line'

    _description = __doc__

    _order = 'sequence asc'

    def _check_sequence(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids, context=context):
            if line.sequence < 0:
                return False
        return True

    def _check_percentages(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids, context=context):
            if (not (0.0 <= line.commission_percentage <= 100.0)) or \
            (not (0.0 <= line.max_discount <= 100.0)):
                return False
        return True

    def _check_monthly_sales(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids, context=context):
            if line.monthly_sales < 0.0:
                return False
        return True

    _columns = {
        'name': fields.char('Name', size=128, required=True),
        'sequence': fields.integer('Sequence', required=True, help='Lower sequence, more priority.'),
        'commission_percentage': fields.float('Commission (%)', digits=(16,2), required=True),
        'commission_rule_id': fields.many2one('sale.commission.rule', string='Commission Rule'),
        'partner_category_id': fields.many2one('res.partner.category', string='Partner Category',
            help='True if empty or the partner belongs to this category.'),
        'pricelist_id': fields.many2one('product.pricelist', string='Pricelist',
            help='True if empty or uses this Pricelist'),
        'payment_term_id': fields.many2one('account.payment.term', string='Payment Term',
            help='True if empty or belongs to the Payment Term'),
        'max_discount': fields.float('Max Discount (%)', digits=(16,2), help='True if empty or met'),
        'monthly_sales': fields.float('Monthly Sales', digits=(16,2), help='True if empty or met.'),
    }

    _constraints = [(_check_sequence, 'Value must be greater or equal than 0.', ['sequence']),
                    (_check_percentages, 'Value must be greater or equal than 0 and lower '
                     'or equal than 100.', ['commission_percentage','max_discount']),
                    (_check_monthly_sales, 'Sales can not be negative', ['monthly_sales'])]

    _sql_constraints = [('unique_sequence_rule','UNIQUE(sequence,commission_rule_id)',
                         'Sequence must be unique for every line in a Commission Rule.')]

class Commission(osv.Model):
    """Commission"""

    _name = 'sale.commission.commission'

    _description = __doc__

    _order = 'invoice_id asc'

    def cancel(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'cancelled'}, context=context)

    def pay(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'paid'}, context=context)

    def expired(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'expired'}, context=context)

    def _check_amount(self, cr, uid, ids, context=None):
        for commission in self.browse(cr, uid, ids, context=context):
            if commission.amount <= 0.0:
                return False
        return True

    def _check_percentage(self, cr, uid, ids, context=None):
        for commission in self.browse(cr, uid, ids, context=context):
            if commission.invoice_commission_percentage <= 0.0 or \
            commission.invoice_commission_percentage > 100.0:
                return False
        return True

    def name_get(self, cr, uid, ids, context=None):
        res = []
        for item in self.browse(cr, uid, ids, context=context):
            res.append((item.id, '%s - %s' % (item.user_id.name,item.invoice_id.number)))
        return res

    _columns = {
        'invoice_id': fields.many2one('account.invoice', string='Invoice', required=True),
        'state': fields.selection([('new','New'),('paid','Paid'),('expired','Expired'),
            ('cancelled','Cancelled')], string='State'),
        'user_id': fields.many2one('res.users', string='Salesperson', required=True),
        'amount': fields.float('Amount', digits=(16,2)),
        'invoice_commission_percentage': fields.float('Commission (%)', digits=(16,2)),
    }

    _constraints = [(_check_amount, 'Value must be greater than 0.', ['amount']),
                    (_check_percentage, 'Value must be greater than 0 and '
                     'lower or equal than 100',['invoice_commission_percentage'])]

    _defaults = {
        'state': 'new',
    }