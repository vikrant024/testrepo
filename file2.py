import base64
import secrets
import uuid
import random
import string
from datetime import datetime
from cerberus import Validator
from django.db.models import Q
from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.utils.decorators import method_decorator

from config.messages import Messages
from utility.argoCommon import ArgoCommon
from utility.loggerService import logerror
from utility.rbacService import RbacService
from utility.hashingUtility import hashingUtility
from utility.authMiddleware import isAuthenticate
from argo_texas.settings import ArgoCommonConstants, EmailConstants
from .serializers import UserSerializer, UserDetailSerializer , NoteSerialiser
from user_auth.models import User, Cities, States, Countries, UserAddresses, Notes
from django.db.models import Value as V
from django.db.models.functions import Concat


# Create your views here.

class Customers(APIView):

    @method_decorator(isAuthenticate)
    @method_decorator(RbacService('customers:profile:read'))
    def get(self, request):
        """
        @api {GET} v1/admin/customers Customer List
        @apiName Customer List
        @apiGroup Admin
        @apiHeader {String} authorization Users unique access-token
        @apiParam {string} search_keyword
        @apiParam {integer} page_limit
        @apiParam {integer} page_offset
        @apiSuccessExample Success-Response:
        HTTP/1.1 200 OK
        {
            "data": [
                {
                    "user_id": 22,
                    "email": "normallogin@yopmail.com",
                    "user_type": {
                        "type_id": 2,
                        "name": "user"
                    },
                    "customer_id": 6598718987,
                    "first_name": "Nitesh",
                    "last_name": "Jangir",
                    "mobile_number": "9876543210",
                    "is_active": 1
                }
            ],
            "total_record": 1
        }
        @apiSuccessExample Success-Response:
        HTTP/1.1 200 OK
        {
            "data": []
        }
        """
        try:
            schema = {
                "search_keyword": {'type': 'string', 'required': True, 'empty': True},
                "page_limit": {'type': 'integer', 'required': True, 'empty': False},
                "page_offset": {'type': 'integer', 'required': True, 'empty': False}
            }
            instance = {
                "search_keyword": request.GET['search_keyword'],
                "page_limit": int(request.GET['page_limit']),
                "page_offset": int(request.GET['page_offset'])
            }
            v = Validator()
            if not v.validate(instance, schema):
                return Response({'error': v.errors}, status=status.HTTP_400_BAD_REQUEST)

            search_keyword = request.GET['search_keyword']
            page_limit = int(request.GET['page_limit'])
            page_offset = int(request.GET['page_offset'])
            query = Q()
            if len(search_keyword) > 0:
                user_info = User.objects.annotate(full_name=Concat('first_name', V(' '), 'last_name')).filter(
                    (Q(full_name__icontains=search_keyword) |
                     Q(customer_id__icontains=search_keyword) |
                     Q(first_name__icontains=search_keyword) |
                     Q(last_name__icontains=search_keyword) |
                     Q(mobile_number__icontains=search_keyword) |
                     Q(company_name__icontains=search_keyword) |
                     Q(email__icontains=search_keyword)) &
                    Q(is_deleted=0) &
                    Q(is_email_verified=1) &
                    Q(is_profile_complete=1) &
                    Q(user_type=2)
                ).all().order_by('-created_at')
                total_record = user_info.count()
                user_info = user_info[page_offset:page_limit + page_offset]
            else:
                query.add(Q(is_deleted=0), Q.AND)
                query.add(Q(is_email_verified=1), Q.AND)
                query.add(Q(is_profile_complete=1), Q.AND)
                query.add(Q(user_type=2), Q.AND)
                user_info = User.objects.filter(query).all().order_by('-created_at')
                total_record = user_info.count()
                user_info = user_info[page_offset:page_limit + page_offset]
            serializer = UserSerializer(user_info, many=True)
            return Response({'data': serializer.data, 'total_record': total_record}, status=status.HTTP_200_OK)
        except Exception as exception:
            logerror('admin_customer/views.py/get', str(exception))
            return Response({'error': str(exception)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # @method_decorator(isAuthenticate)
    # @method_decorator(RbacService('customers:profile:create'))
    def post(self, request):
        """
        @api {POST} v1/admin/customers Customer Create
        @apiName Customer Create
        @apiGroup Admin
        @apiHeader {String} authorization Users unique access-token
        @apiParam {string} first_name
        @apiParam {string} last_name
        @apiParam {string} gender allowed `male`, `female`
        @apiParam {string} marital_status allowed `single`, `married`
        @apiParam {string} mobile
        @apiParam {string} phone
        @apiParam {string} email
        @apiParam {string} mailing_address
        @apiParam {integer} mailing_country_id
        @apiParam {integer} mailing_state_id
        @apiParam {integer} mailing_city_id
        @apiParam {integer} mailing_zip_code
        @apiParam {string} physical_address
        @apiParam {integer} physical_country_id
        @apiParam {integer} physical_state_id
        @apiParam {integer} physical_city_id
        @apiParam {integer} physical_zip_code
        @apiParam {string} id_type allowed `license`, `passport`, `stateid`, `foreginid`
        @apiParam {string} id_number allowed `license`, `passport`, `stateid`, `foreginid`
        @apiParam {integer} id_country
        @apiParam {integer} id_state
        @apiParam {date} id_expire_date format `yyyy-mm-dd`
        @apiParam {string} id_status allowed `valid`, `expired`, `suspended`, `revoked`
        @apiSuccessExample Success-Response:
        HTTP/1.1 201 CREATED
        {
            "message": "Customer created"
        }
        @apiErrorExample Error-Response:
        HTTP/1.1 200 OK
        {
            "error": "Email already exists"
        }
        """
        try:
            schema = {
                "first_name": {'type': 'string', 'required': True, 'empty': False},
                "last_name": {'type': 'string', 'required': True, 'empty': False},
                "gender": {'type': 'string', 'required': True, 'empty': False, 'allowed': ArgoCommonConstants.GENDER},
                "dob": {'type': 'date', 'required': True, 'empty': False},
                "marital_status": {'type': 'string', 'required': True, 'empty': False,
                                   'allowed': ArgoCommonConstants.MARTIAL_STATUS},
                "country_code": {'type': 'integer', 'required': True, 'empty': False},
                "ssn_itin": {'type': 'string', 'required': True, 'empty': True},
                "mobile": {'type': 'string', 'required': True, 'empty': False},
                "phone": {'type': 'string', 'required': True, 'empty': False},
                "email": {'type': 'string', 'required': True, 'empty': False},
                "profile_type": {'type': 'string', 'required': True, 'empty': False,
                                 'allowed': ArgoCommonConstants.PROFILE_TYPES},
                "company_name": {'type': 'string', 'required': True, 'empty': True},
                "mailing_address": {'type': 'string', 'required': True, 'empty': False},
                "mailing_country_id": {'type': 'integer', 'required': True, 'nullable': False},
                "mailing_state_id": {'type': 'integer', 'required': True, 'nullable': False},
                "mailing_city_id": {'type': 'integer', 'required': True, 'nullable': False},
                "mailing_zip_code": {'type': 'integer', 'required': True, 'nullable': False},
                "physical_address": {'type': 'string', 'required': True, 'empty': False},
                "physical_country_id": {'type': 'integer', 'required': True, 'nullable': False},
                "physical_state_id": {'type': 'integer', 'required': True, 'nullable': False},
                "physical_city_id": {'type': 'integer', 'required': True, 'nullable': False},
                "physical_zip_code": {'type': 'integer', 'required': True, 'nullable': False},
                "id_type": {'type': 'string', 'required': True, 'empty': False,
                            'allowed': ArgoCommonConstants.ID_TYPE},
                "id_number": {'type': 'string', 'required': True, 'empty': False},
                "id_country": {'type': 'integer', 'required': True, 'nullable': False},
                "id_state": {'type': 'integer', 'required': True, 'nullable': True},
                "id_expire_date": {'type': 'date', 'required': True, 'empty': False},
                "id_status": {'type': 'string', 'required': True, 'empty': False,
                              'allowed': ArgoCommonConstants.ID_STATUS}
            }
            request.data.update({'dob': datetime.strptime(request.data.get('dob'), '%Y-%m-%d')})
            request.data.update({'id_expire_date': datetime.strptime(request.data.get('id_expire_date'), '%Y-%m-%d')})
            v = Validator()
            if not v.validate(request.data, schema):
                return Response({'error': v.errors}, status=status.HTTP_400_BAD_REQUEST)

            if User.objects.filter(email=request.data.get('email').lower()).exists():
                # generate a random hex key
                token_value = secrets.token_hex(20)

                # encode the email
                email_token = base64.b64encode(request.data.get('email').encode('utf-8', 'strict'))

                # generate a link to send over mail
                link = EmailConstants.verificationLink + "verify-email?tokenValue=" + token_value \
                       + "&token=" + email_token.decode('utf-8')

                ArgoCommon().sendVerificationLink("user", request.data.get('email'), link)
                return Response({'error': Messages.EMAIL_EXITS_AND_EMAIL_SENT}, status=status.HTTP_200_OK)

            state_obj = None
            if request.data.get('id_state'):
                state_obj = States.objects.get(state_id=request.data.get('id_state'))

            country_obj = Countries.objects.get(country_id=request.data.get('id_country'))

            # generate random password
            special_characters = '@#$&'
            password = ''.join(random.choice(string.ascii_lowercase) for i in range(6))
            password = password + ''.join(random.choice(string.ascii_uppercase))
            password = password + ''.join(random.choice(string.digits))
            password = password + ''.join(random.choice(special_characters))

            # Encrypted password
            utility = hashingUtility()
            hashed_model = utility.getHashedPassword(password)
            customer_id = random.randint(1111111111, 9999999999)

            # generate uuid
            user_uuid = uuid.uuid1()

            # atomic transactions
            with transaction.atomic():

                User.objects.create(
                    email=request.data.get('email'),
                    customer_id=customer_id,
                    uuid=user_uuid,
                    password=str(hashed_model.Password, 'utf-8'),
                    password_salt=str(hashed_model.Salt, 'utf-8'),
                    first_name=request.data.get('first_name'),
                    last_name=request.data.get('last_name'),
                    gender=request.data.get('gender'),
                    dob=request.data.get('dob'),
                    profile_type=request.data.get('profile_type'),
                    company_name=request.data.get('company_name'),
                    marital_status=request.data.get('marital_status'),
                    ssn_itin=request.data.get('ssn_itin'),
                    country_code=request.data.get('country_code'),
                    mobile_number=request.data.get('mobile'),
                    phone_number=request.data.get('phone'),
                    id_type=request.data.get('id_type'),
                    state_id=state_obj,
                    country_id=country_obj,
                    id_expiry_date=request.data.get('id_expire_date'),
                    id_status=request.data.get('id_status'),
                    id_number=request.data.get('id_number'),
                    is_email_verified=1,
                    is_profile_complete=1
                )
                user_obj = User.objects.latest('user_id')
                physical_city_obj = Cities.objects.get(city_id=request.data.get('physical_city_id'))
                physical_state_obj = States.objects.get(state_id=request.data.get('physical_state_id'))
                UserAddresses.objects.create(
                    user_id=user_obj,
                    city=physical_city_obj,
                    state=physical_state_obj,
                    country_id=physical_state_obj.country_id,
                    address=request.data.get('physical_address'),
                    zip_code=request.data.get('physical_zip_code'),
                    address_type='physical'
                )
                mailing_city_obj = Cities.objects.get(city_id=request.data.get('mailing_city_id'))
                mailing_state_obj = States.objects.get(state_id=request.data.get('mailing_state_id'))
                UserAddresses.objects.create(
                    user_id=user_obj,
                    city=mailing_city_obj,
                    state=mailing_state_obj,
                    country_id=mailing_state_obj.country_id,
                    address=request.data.get('mailing_address'),
                    zip_code=request.data.get('mailing_zip_code'),
                    address_type='mailing'
                )
                ArgoCommon.sendAccountCreationMail(
                    request.data.get('first_name'),
                    request.data.get('email'),
                    password,
                    str(customer_id)
                )
                return Response({'message': Messages.CUSTOMER_CREATED}, status=status.HTTP_201_CREATED)

        except Exception as exception:
            logerror('admin_customer/views.py/create', str(exception))
            return Response({'error': str(exception)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerDetail(APIView):
    # get customer details
    # @method_decorator(isAuthenticate)
    # @method_decorator(RbacService('customers:profile:read'))
    def get(self, request, id):
        """
        @api {GET} v1/admin/customers/<int:id> Customer details
        @apiName Customer details
        @apiGroup Admin
        @apiHeader {String} authorization Users unique access-token
        @apiParam {integer} id
        @apiSuccessExample Success-Response:
        HTTP/1.1 200 OK
        {
            "user_id": 163,
            "email": "nitesh.new1@yopmail.com",
            "customer_id": 3841201203,
            "first_name": "Nitesh",
            "last_name": "Jangir",
            "gender": "male",
            "marital_status": "single",
            "mobile_number": "21772",
            "phone_number": "123123",
            "id_type": "license",
            "state_id": {
                "state_id": 1,
                "state_name": "California",
                "country_id": 1
            },
            "country_id": {
                "country_id": 1,
                "country_name": "USA",
                "country_code": 1,
                "country_short_code": "USA"
            },
            "id_expiry_date": "2020-01-11",
            "id_status": "valid",
            "id_number": "FU477DJJHD",
            "is_active": 1,
            "user_addresses": [
                {
                    "address_id": 2,
                    "user_id": 163,
                    "city": {
                        "city_id": 1,
                        "state_id": 1,
                        "city_name": "Los Angeles"
                    },
                    "state": {
                        "state_id": 1,
                        "state_name": "California",
                        "country_id": 1
                    },
                    "country_id": {
                        "country_id": 1,
                        "country_name": "USA",
                        "country_code": 1,
                        "country_short_code": "USA"
                    },
                    "address": "dsfsdfds",
                    "zip_code": 12312,
                    "address_type": "physical",
                    "created_at": "2020-09-08T07:33:23Z"
                },
                {
                    "address_id": 3,
                    "user_id": 163,
                    "city": {
                        "city_id": 1,
                        "state_id": 1,
                        "city_name": "Los Angeles"
                    },
                    "state": {
                        "state_id": 1,
                        "state_name": "California",
                        "country_id": 1
                    },
                    "country_id": {
                        "country_id": 1,
                        "country_name": "USA",
                        "country_code": 1,
                        "country_short_code": "USA"
                    },
                    "address": "dsfsdfds",
                    "zip_code": 12312,
                    "address_type": "mailing",
                    "created_at": "2020-09-08T09:30:12Z"
                }
            ]
        }
        """
        try:
            current_user_id = int(3)
            user_info = User.objects.filter(user_id=current_user_id, is_deleted=0)
            if not user_info.exists():
                return Response({'error': Messages.USER_NOT_EXIST}, status=status.HTTP_200_OK)
            # user_info = User.objects.filter(user_id=current_user_id)
            serializer = UserDetailSerializer(user_info, many=True)
            return Response(serializer.data[0], status=status.HTTP_200_OK)
        except Exception as exception:
            logerror('admin_customer/views.py/CustomerDetail', str(exception))
            return Response({'error': str(exception)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @method_decorator(isAuthenticate)
    @method_decorator(RbacService('customers:profile:update'))
    def put(self, request, id):
        """
        @api {PUT} v1/admin/customers/<int:id> Customer Update
        @apiName Customer Update
        @apiGroup Admin
        @apiHeader {String} authorization Users unique access-token
        @apiParam {integer} id
        @apiParam {string} first_name
        @apiParam {string} last_name
        @apiParam {string} gender allowed `male`, `female`, `others`
        @apiParam {string} marital_status allowed `single`, `married`
        @apiParam {string} mobile
        @apiParam {string} phone
        @apiParam {string} mailing_address
        @apiParam {integer} mailing_country_id
        @apiParam {integer} mailing_state_id
        @apiParam {integer} mailing_city_id
        @apiParam {integer} mailing_zip_code
        @apiParam {string} physical_address
        @apiParam {integer} physical_country_id
        @apiParam {integer} physical_state_id
        @apiParam {integer} physical_city_id
        @apiParam {integer} physical_zip_code
        @apiParam {string} id_type allowed `license`, `passport`, `stateid`, `foreginid`
        @apiParam {string} id_number allowed `license`, `passport`, `stateid`, `foreginid`
        @apiParam {integer} id_country
        @apiParam {integer} id_state
        @apiParam {date} id_expire_date format `yyyy-mm-dd`
        @apiParam {string} id_status allowed `valid`, `expired`, `suspended`, `revoked`
        @apiSuccessExample Success-Response:
        HTTP/1.1 200 OK
        {
            "message": "User details has been updated"
        }
        @apiErrorExample Error-Response:
        HTTP/1.1 200 OK
        {
            "error": "User does not exist"
        }
        """
        try:
            schema = {
                "first_name": {'type': 'string', 'required': True, 'empty': False},
                "last_name": {'type': 'string', 'required': True, 'empty': False},
                "gender": {'type': 'string', 'required': True, 'empty': False, 'allowed': ['male', 'female']},
                "dob": {'type': 'date', 'required': True, 'empty': False},
                "marital_status": {'type': 'string', 'required': True, 'empty': False,
                                   'allowed': ['single', 'married', 'separated']},
                "country_code": {'type': 'integer', 'required': True, 'empty': False},
                "ssn_itin": {'type': 'string', 'required': True, 'empty': True},
                "mobile": {'type': 'string', 'required': True, 'empty': False},
                "phone": {'type': 'string', 'required': True, 'empty': False},
                "profile_type": {'type': 'string', 'required': True, 'empty': False,
                                 'allowed': ArgoCommonConstants.PROFILE_TYPES},
                "company_name": {'type': 'string', 'required': True, 'empty': True},
                "mailing_address": {'type': 'string', 'required': True, 'empty': False},
                "mailing_country_id": {'type': 'integer', 'required': True, 'nullable': False},
                "mailing_state_id": {'type': 'integer', 'required': True, 'nullable': False},
                "mailing_city_id": {'type': 'integer', 'required': True, 'nullable': False},
                "mailing_zip_code": {'type': 'integer', 'required': True, 'nullable': False},
                "physical_address": {'type': 'string', 'required': True, 'empty': False},
                "physical_country_id": {'type': 'integer', 'required': True, 'nullable': False},
                "physical_state_id": {'type': 'integer', 'required': True, 'nullable': False},
                "physical_city_id": {'type': 'integer', 'required': True, 'nullable': False},
                "physical_zip_code": {'type': 'integer', 'required': True, 'nullable': False},
                "id_type": {'type': 'string', 'required': True, 'empty': False,
                            'allowed': ['license', 'passport', 'stateid', 'foreginid']},
                "id_number": {'type': 'string', 'required': True, 'empty': False},
                "id_country": {'type': 'integer', 'required': True, 'nullable': False},
                "id_state": {'type': 'integer', 'required': True, 'nullable': True},
                "id_expire_date": {'type': 'date', 'required': True, 'empty': False},
                "id_status": {'type': 'string', 'required': True, 'empty': False,
                              'allowed': ['valid', 'expired', 'suspended', 'revoked']}
            }
            request.data.update({'dob': datetime.strptime(request.data.get('dob'), '%Y-%m-%d')})
            request.data.update({'id_expire_date': datetime.strptime(request.data.get('id_expire_date'), '%Y-%m-%d')})
            v = Validator()
            if not v.validate(request.data, schema):
                return Response({'error': v.errors}, status=status.HTTP_400_BAD_REQUEST)
            current_user_id = int(id)
            if (not User.objects.filter(user_id=current_user_id).exists() or
                    User.objects.filter(user_id=current_user_id, is_deleted=1).exists()):
                return Response({'error': Messages.USER_NOT_EXIST}, status=status.HTTP_200_OK)
            user_obj = User.objects.get(user_id=current_user_id)

            state_obj = None
            if request.data.get('id_state'):
                state_obj = States.objects.get(state_id=request.data.get('id_state'))

            country_obj = Countries.objects.get(country_id=request.data.get('id_country'))

            # atomic transactions
            with transaction.atomic():

                User.objects.filter(user_id=current_user_id).update(
                    first_name=request.data.get('first_name'),
                    last_name=request.data.get('last_name'),
                    gender=request.data.get('gender'),
                    dob=request.data.get('dob'),
                    profile_type=request.data.get('profile_type'),
                    company_name=request.data.get('company_name'),
                    marital_status=request.data.get('marital_status'),
                    country_code=request.data.get('country_code'),
                    ssn_itin=request.data.get('ssn_itin'),
                    mobile_number=request.data.get('mobile'),
                    phone_number=request.data.get('phone'),
                    id_type=request.data.get('id_type'),
                    state_id=state_obj,
                    country_id=country_obj,
                    id_expiry_date=request.data.get('id_expire_date'),
                    id_status=request.data.get('id_status'),
                    id_number=request.data.get('id_number')
                )
                physical_city_obj = Cities.objects.get(city_id=request.data.get('physical_city_id'))
                physical_state_obj = States.objects.get(state_id=request.data.get('physical_state_id'))
                # if physical address already exist then update
                if UserAddresses.objects.filter(user_id=current_user_id, address_type='physical').exists():
                    UserAddresses.objects.filter(
                        user_id=current_user_id, address_type='physical'
                    ).update(
                        city=physical_city_obj,
                        state=physical_state_obj,
                        country_id=physical_state_obj.country_id,
                        address=request.data.get('physical_address'),
                        zip_code=request.data.get('physical_zip_code')
                    )
                else:
                    UserAddresses.objects.create(
                        user_id=user_obj,
                        city=physical_city_obj,
                        state=physical_state_obj,
                        country_id=physical_state_obj.country_id,
                        address=request.data.get('physical_address'),
                        zip_code=request.data.get('physical_zip_code'),
                        address_type='physical'
                    )
                mailing_city_obj = Cities.objects.get(city_id=request.data.get('mailing_city_id'))
                mailing_state_obj = States.objects.get(state_id=request.data.get('mailing_state_id'))
                # if mailing address already exist then update
                if UserAddresses.objects.filter(user_id=current_user_id, address_type='mailing').exists():
                    UserAddresses.objects.filter(
                        user_id=current_user_id, address_type='mailing'
                    ).update(
                        city=mailing_city_obj,
                        state=mailing_state_obj,
                        country_id=mailing_state_obj.country_id,
                        address=request.data.get('mailing_address'),
                        zip_code=request.data.get('mailing_zip_code')
                    )
                else:
                    UserAddresses.objects.create(
                        user_id=user_obj,
                        city=mailing_city_obj,
                        state=mailing_state_obj,
                        country_id=mailing_state_obj.country_id,
                        address=request.data.get('mailing_address'),
                        zip_code=request.data.get('mailing_zip_code'),
                        address_type='mailing'
                    )
                return Response({'message': Messages.USER_UPDATED}, status=status.HTTP_200_OK)
        except Exception as exception:
            logerror('admin_customer/views.py/CustomerDetail', str(exception))
            return Response({'error': str(exception)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
# @isAuthenticate
# @RbacService('customers:profile:update')
def create_note(request):
    """
    @api {POST} v1/user/profile/update Update user profile
    @apiName Update user profile
    @apiGroup User
    @apiHeader {String} authorization Users unique access-token
    @apiParam {string} image
    @apiParam {string} first_name
    @apiParam {string} last_name
    @apiParam {date} dob
    @apiParam {string} address
    @apiParam {integer} city_id
    @apiParam {integer} state_id
    @apiParam {integer} zip_code
    @apiParam {integer} country_code
    @apiParam {integer} phone
    @apiSuccessExample Success-Response:
    HTTP/1.1 200 OK
    {
        "message": "A link is sent to your Registred email address"
    }
    @apiErrorExample Error-Response:
    HTTP/1.1 200 OK
    {
        "error": "Email id not registered"
    }
    """
    try:
        
        schema = {
            "user_id": {'type': 'integer', 'required': True, 'empty': False},
            "user_note": {'type': 'string', 'required': True, 'empty': False},
            "full_name": {'type':'string', 'required': True,'empty':False},
            "role_id": {'type': 'integer', 'required': True, 'nullable': False},
        }
        v = Validator()
        if not v.validate(request.data, schema):
            return Response({'error': v.errors}, status=status.HTTP_400_BAD_REQUEST)

        user_obj = User.objects.get(user_id=request.data.get('user_id'))
        if user_obj:
            note =request.data.get('user_note')
            full_name = request.data.get('full_name')
            role_id = request.data.get('role_id')
            Notes.objects.create(
                user_id=user_obj,
                user_notes= note,
                agent_name = full_name,
                agent_id_id = role_id
                
                
                )
            
            # agent_id=1
            message = Messages.USER_NOTE_CREATED
            return Response({'message': message}, status=status.HTTP_201_CREATED)
    except Exception as exception:
        logerror('user/views.py/create_note', str(exception))
        return Response({'error': str(exception)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
# @isAuthenticate
# @RbacService('customers:profile:update')
def notes_list(request):
    
    try:
            schema = {
                # "search_keyword": {'type': 'string', 'required': True, 'empty': True},
                "page_limit": {'type': 'integer', 'required': True, 'empty': False},
                "page_offset": {'type': 'integer', 'required': True, 'empty': False}
            }
            instance = {
                # "search_keyword": request.GET['search_keyword'],
                "page_limit": int(request.GET['page_limit']),
                "page_offset": int(request.GET['page_offset'])
            }
            v = Validator()
            if not v.validate(instance, schema):
                return Response({'error': v.errors}, status=status.HTTP_400_BAD_REQUEST)

            # search_keyword = request.GET['search_keyword']
            page_limit = int(request.GET['page_limit'])
            page_offset = int(request.GET['page_offset'])
            data=Notes.objects.all()
            user_info = data[page_offset:page_limit + page_offset]
            serializer = NoteSerialiser(data, many=True)
            return Response({'data':serializer.data}, status=status.HTTP_200_OK)
    except Exception as exception:
        logerror('user/views.py/notes_list', str(exception))
        return Response({'error': str(exception)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
# @isAuthenticate
# @RbacService('customers:profile:update')
def delete_note(request ,id ):
    """
    @api {POST} v1/user/profile/update Update user profile
    @apiName Update user profile
    @apiGroup User
    @apiHeader {String} authorization Users unique access-token
    @apiParam {string} image
    @apiParam {string} first_name
    @apiParam {string} last_name
    @apiParam {date} dob
    @apiParam {string} address
    @apiParam {integer} city_id
    @apiParam {integer} state_id
    @apiParam {integer} zip_code
    @apiParam {integer} country_code
    @apiParam {integer} phone
    @apiSuccessExample Success-Response:
    HTTP/1.1 200 OK
    {
        "message": "A link is sent to your Registred email address"
    }
    @apiErrorExample Error-Response:
    HTTP/1.1 200 OK
    {
        "error": "Email id not registered"
    }
    """
    try:
        note_id = int(id)
        id_obj = Notes.objects.filter(id=note_id)
        if id_obj.exists():
            id_obj.delete()
            return Response({'message': Messages.USER_NOTE_DELETED}, status=status.HTTP_200_OK)
        return Response({'message': Messages.USER_NOTE_NOT_FOUND}, status=status.HTTP_200_OK)
    except Exception as exception:
        logerror('admin_customer/views.py/delete_note', str(exception))
        return Response({'error': str(exception)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
# @isAuthenticate
def update_note(request, id):
    """
    @api {GET} v1/admin/customers/document/delete/<int:id> Delete User documents
    @apiName Delete User documents
    @apiGroup Admin
    @apiHeader {String} authorization Users unique access-token
    @apiSuccessExample Success-Response:
    HTTP/1.1 200 OK
    {
        "message": "Document deleted successfully"
    }
    @apiErrorExample Error-Response:
    HTTP/1.1 200 OK
    {
        "message": "Document not found"
    }
    """
    
    try:
        schema = {
            "id": {'type': 'integer', 'required': True, 'empty': False},
            "user_notes": {'type': 'string', 'required': True, 'empty': True}
                }
        print(request.data)
        
        v = Validator()
        if not v.validate(request.data, schema):
            return Response({'error': v.errors}, status=status.HTTP_400_BAD_REQUEST)
        note_id = int(id)
        id_obj = Notes.objects.filter(id=note_id)
        user_notes = request.data.get('user_notes')
        if id_obj.exists():
            id_obj.update(
               user_notes = request.data.get('user_notes')
            )
            return Response({'message': Messages.USER_NOTE_UPDATED}, status=status.HTTP_200_OK)
        return Response({'message': Messages.USER_NOTE_NOT_FOUND}, status=status.HTTP_200_OK)
    except Exception as exception:
        logerror('admin_customer/views.py/update_note', str(exception))
        return Response({'error': str(exception)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
