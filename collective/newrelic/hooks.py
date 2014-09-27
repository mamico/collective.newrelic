from AccessControl import getSecurityManager
from collective.newrelic.utils import logger
from zope.browser.interfaces import IBrowserView
from zope.browserresource.interfaces import IResource
from zope.pagetemplate.interfaces import IPageTemplate
import newrelic.agent
import newrelic.api
import os
from collective.newrelic.patches.zserverpublisher import PLACEHOLDER

# IPubAfterTraversal hook for naming our transactions!


def newrelic_transaction(event):

    try:
        request = event.request
        published = request.get('PUBLISHED', None)
        trans = newrelic.agent.current_transaction()

        try:
            klass = published.__class__
        except AttributeError:
            transname = PLACEHOLDER
        else:
            if klass.__module__ == 'Products.Five.metaclass':
                if klass.__bases__[0].__name__ == 'ViewMixinForTemplates':
                    try:
                        transname = os.path.basename(klass.index.filename)
                    except:
                        transname = PLACEHOLDER
                else:
                    klass = klass.__bases__[0]
                    transname = klass.__module__ + '.' + klass.__name__
            elif klass.__name__ in ('FSPageTemplate', 'FSControllerPageTemplate'):
                transname = os.path.basename(published._filepath)
            else:
                transname = klass.__module__ + '.' + klass.__name__

        if trans:
            # We only want to track the following:
            # 1. BrowserViews (but not the resource kind ..)
            # 2. PageTemplate (/skins/*/*.pt ) being used as views
            # 3. PageTemplate's in ZMI
            if (IBrowserView.providedBy(published) or IPageTemplate.providedBy(published)) and not IResource.providedBy(published):
                trans.name_transaction(transname, group='Zope2', priority=1)
                user = getSecurityManager().getUser()
                user_id = user.getId() if user else ''
                newrelic.agent.add_custom_parameter('user', user_id)
                if hasattr(published, 'context'):  # Plone
                    newrelic.agent.add_custom_parameter('id', published.context.id)
                    newrelic.agent.add_custom_parameter('absolute_url', published.context.absolute_url())
                elif hasattr(published, 'id') and hasattr(published, 'absolute_url'):  # Zope
                    newrelic.agent.add_custom_parameter('id', published.id)
                    newrelic.agent.add_custom_parameter('absolute_url', published.absolute_url())
                else:
                    # We don't know what it is .. so no custom parameters!
                    logger.debug("Published has no context nor an id/absolute_url. Skipping custom parameters")

                logger.debug("Transaction: {0}".format(transname))
            else:
                # For debugging purpose
                logger.debug("NO transaction? : {0}   Browser: {1}  Resource: {2} PageTemplate: {3}".format(
                    transname,
                    IBrowserView.providedBy(published),
                    IResource.providedBy(published),
                    IPageTemplate.providedBy(published)))

    except Exception, e:
        # Log it and carry on.
        logger.exception(e)
