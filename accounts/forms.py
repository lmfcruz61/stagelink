from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from .models import Artist, ArtistPhoto, ContactMessage, Fan, NewsletterSubscriber, Organization, OrganizationMember, Profile


class SignUpForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=(
            (Profile.MUSICIAN, 'Artista'),
            (Profile.FAN, 'Publico'),
        ),
        label='Tipo de conta',
    )
    display_name = forms.CharField(max_length=120, label='Nome público')
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'display_name', 'role', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Este email ja esta associado a uma conta. Usa esse login para gerir varios artistas.')
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            role = self.cleaned_data['role']
            display_name = self.cleaned_data['display_name']
            Profile.objects.create(user=user, role=role)
            if role == Profile.MUSICIAN:
                Artist.objects.create(user=user, name=display_name)
            else:
                Fan.objects.create(user=user, display_name=display_name)
        return user


class ArtistProfileForm(forms.ModelForm):
    photo = forms.ImageField(
        label='Foto principal',
        required=False,
        help_text='Recomendado: imagem quadrada, pelo menos 800x800 px, em JPG ou PNG.',
    )
    hero_image = forms.ImageField(
        label='Imagem de capa da pagina',
        required=False,
        help_text='Recomendado: imagem horizontal 16:9, pelo menos 1600x900 px.',
    )

    class Meta:
        model = Artist
        fields = (
            'name',
            'headline',
            'monetization_mode',
            'location',
            'bio',
            'contact_email',
            'contact_phone',
            'photo',
            'hero_image',
            'youtube_link',
            'instagram_link',
            'spotify_link',
            'website_link',
        )
        labels = {
            'name': 'Nome artistico',
            'headline': 'Frase de destaque',
            'monetization_mode': 'Modo de monetizacao',
            'location': 'Cidade / pais',
            'bio': 'Bio',
            'contact_email': 'Email de contacto',
            'contact_phone': 'Telefone de contacto',
            'photo': 'Foto principal',
            'hero_image': 'Imagem de capa da pagina',
            'youtube_link': 'Link YouTube',
            'instagram_link': 'Link Instagram',
            'spotify_link': 'Link Spotify',
            'website_link': 'Site oficial',
        }
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 6}),
        }
        help_texts = {
            'monetization_mode': (
                'Escolhe como este artista ganha dinheiro: somente subscricao, '
                'subscricao com material pago exclusivo para subscritores, ou material pago aberto a todos.'
            ),
        }


class ManagedArtistForm(ArtistProfileForm):
    class Meta(ArtistProfileForm.Meta):
        fields = ArtistProfileForm.Meta.fields


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ('name', 'description', 'website', 'logo')
        labels = {
            'name': 'Nome',
            'description': 'Descricao',
            'website': 'Site',
            'logo': 'Logotipo',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class OrganizationMemberForm(forms.ModelForm):
    username = forms.CharField(label='Username do utilizador')

    class Meta:
        model = OrganizationMember
        fields = ('username', 'role')
        labels = {
            'role': 'Permissao',
        }


class FanProfileForm(forms.ModelForm):
    photo = forms.ImageField(
        label='Foto de perfil',
        required=False,
        help_text='Recomendado: imagem quadrada, pelo menos 400x400 px, em JPG ou PNG.',
    )

    class Meta:
        model = Fan
        fields = ('display_name', 'photo')
        labels = {
            'display_name': 'Nome publico',
            'photo': 'Foto de perfil',
        }
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 5}),
        }


class ArtistPhotoForm(forms.ModelForm):
    image = forms.ImageField(
        label='Foto da galeria',
        help_text='Recomendado: pelo menos 1200 px de largura, em JPG ou PNG.',
    )

    class Meta:
        model = ArtistPhoto
        fields = ('image', 'caption')
        labels = {
            'image': 'Foto da galeria',
            'caption': 'Legenda',
        }


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'multiple': True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(file, initial) for file in data]
        return [single_file_clean(data, initial)] if data else []


class ArtistGalleryUploadForm(forms.Form):
    MAX_UPLOAD_IMAGES = 10
    MAX_IMAGE_SIZE = 5 * 1024 * 1024
    MAX_TOTAL_SIZE = 30 * 1024 * 1024
    ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp'}

    images = MultipleFileField(
        label='Fotos para a galeria',
        help_text='Maximo 10 fotos por envio, 5 MB por foto e 30 MB no total. Usa JPG, PNG ou WebP.',
    )
    caption = forms.CharField(
        label='Legenda comum',
        max_length=140,
        required=False,
        help_text='Opcional. Sera aplicada a todas as fotos deste envio.',
    )

    def clean_images(self):
        images = self.cleaned_data['images']
        if len(images) > self.MAX_UPLOAD_IMAGES:
            raise forms.ValidationError(f'Envia no maximo {self.MAX_UPLOAD_IMAGES} fotos de cada vez.')
        if sum(image.size for image in images) > self.MAX_TOTAL_SIZE:
            raise forms.ValidationError('Cada envio pode ter no maximo 30 MB no total.')
        for image in images:
            content_type = getattr(image, 'content_type', '')
            if content_type not in self.ALLOWED_CONTENT_TYPES:
                raise forms.ValidationError('Usa apenas imagens JPG, PNG ou WebP.')
            if image.size > self.MAX_IMAGE_SIZE:
                raise forms.ValidationError('Cada foto pode ter no maximo 5 MB.')
        return images


class NewsletterSubscriberForm(forms.ModelForm):
    class Meta:
        model = NewsletterSubscriber
        fields = ('name', 'email', 'interest_type')
        labels = {
            'name': 'Nome',
            'email': 'Email',
            'interest_type': 'Tipo de interesse',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'O teu nome'}),
            'email': forms.EmailInput(attrs={'placeholder': 'email@exemplo.com'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if NewsletterSubscriber.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Este email ja esta subscrito na newsletter.')
        return email


class ContactForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = ContactMessage
        fields = ('name', 'email', 'contact_type', 'subject', 'message')
        labels = {
            'name': 'Nome',
            'email': 'Email',
            'contact_type': 'Tipo de contacto',
            'subject': 'Assunto',
            'message': 'Mensagem',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'O teu nome'}),
            'email': forms.EmailInput(attrs={'placeholder': 'email@exemplo.com'}),
            'subject': forms.TextInput(attrs={'placeholder': 'Resumo do pedido'}),
            'message': forms.Textarea(attrs={'rows': 7, 'placeholder': 'Escreve a tua mensagem'}),
        }

    def clean_website(self):
        value = self.cleaned_data.get('website', '')
        if value:
            raise forms.ValidationError('Mensagem bloqueada.')
        return value

    def clean_name(self):
        return self.cleaned_data['name'].strip()

    def clean_subject(self):
        subject = self.cleaned_data['subject'].strip()
        if len(subject) < 3:
            raise forms.ValidationError('Escreve um assunto um pouco mais claro.')
        return subject

    def clean_message(self):
        message = self.cleaned_data['message'].strip()
        if len(message) < 10:
            raise forms.ValidationError('Escreve uma mensagem com mais detalhe.')
        return message
