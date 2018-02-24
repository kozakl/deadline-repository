from __future__ import print_function
import Draft
import datetime
import string 
import re

anchorDict = {'NorthWest':Draft.Anchor.NorthWest, 'NorthCenter':Draft.Anchor.North, 'NorthEast':Draft.Anchor.NorthEast, 'SouthWest':Draft.Anchor.SouthWest, 'SouthCenter':Draft.Anchor.South, 'SouthEast':Draft.Anchor.SouthEast}
framePadding = "####"
    
def Translate( text, img, frame ):
    global framePadding

    # This will only occur when the Draft job is submitted. Add padding to frame.
    if type( frame ) == int:
        if len( str( frame ) ) <= len( framePadding ):
            extraPadding = "0" * ( len( framePadding ) - len( str( frame ) ) )
            frame = extraPadding + str( frame )

    text = text.replace( "$frame", str( frame ) )
    text = text.replace( "$time", datetime.datetime.now().strftime("%m/%d/%Y %I:%M %p") )
    text = text.replace( "$dimensions", str( img.width ) + 'x' + str( img.height ) )
    return text

def IsNotEmpty( text ):
    return text and len( text.strip() ) != 0

def CompositeSingleAnnotationOverImg( img, anchor, text, frame, annotationInfo ):
    if text.startswith( "$logo" ):
        try:
            m = re.match( "^(\$logo)\((.*)\)$", text )
            logo = Draft.Image.ReadFromFile( str( m.group(2) ).strip() )
            logo.SetChannel( 'A', 0.3 )
            logoHeight = int( img.height * 0.045 )
            logo.Resize( int( logoHeight * float( logo.width ) / logo.height ), logoHeight )
            img.CompositeWithAnchor( logo, anchorDict[anchor], Draft.CompositeOperator.OverCompositeOp )
        except:
            warningMsg = "Failed to read logo from file. No logo will be added. The required format $logo( path//to//logo ) might be incorrect."
            print(warningMsg)
    else:
        annotation = Draft.Image.CreateAnnotation( Translate( text, img, frame ), annotationInfo )
        img.CompositeWithAnchor( annotation, anchorDict[anchor], Draft.CompositeOperator.OverCompositeOp )

def DrawSingleAnnotation( img, anchor, textInfo, frame=-1 ):
    global framePadding
    
    if frame == -1:
        frame = framePadding

    text = textInfo[ 'text' ]

    if text and len( text.strip() ) != 0:
        annotationInfo = Draft.AnnotationInfo()
        annotationInfo.BackgroundColor = Draft.ColorRGBA( 0.0, 0.0, 0.0, 0.0 )
        annotationInfo.PointSize = int( img.height * 0.045 )

        if "" not in ( textInfo[ 'colorR' ], textInfo[ 'colorG' ], textInfo[ 'colorB' ] ):
            redColor = int( textInfo[ 'colorR' ] ) / float( 255 )
            greenColor = int( textInfo[ 'colorG' ] ) / float( 255 )
            blueColor = int( textInfo[ 'colorB' ] ) / float( 255 )
            annotationInfo.Color = Draft.ColorRGBA( redColor, greenColor, blueColor, 1 )
        else:
            annotationInfo.Color = Draft.ColorRGBA( 1.0, 1.0, 1.0, 1.0 )

        CompositeSingleAnnotationOverImg( img, anchor, text, frame, annotationInfo )

def DrawAllAnnotations( img, annotations, frame=-1 ):
    global framePadding

    if frame == -1:
        frame = framePadding

    annotationInfo = Draft.AnnotationInfo()
    annotationInfo.BackgroundColor = Draft.ColorRGBA( 0.0, 0.0, 0.0, 0.0 )
    annotationInfo.PointSize = int( img.height * 0.045 )

    for anchor, textInfo in annotations.iteritems():
        text = textInfo['text']

        if "" not in ( textInfo[ 'colorR' ], textInfo[ 'colorG' ], textInfo[ 'colorB' ] ):
            redColor = int( textInfo[ 'colorR' ] ) / float( 255 )
            greenColor = int( textInfo[ 'colorG' ] ) / float( 255 )
            blueColor = int( textInfo[ 'colorB' ] ) / float( 255 )
            annotationInfo.Color = Draft.ColorRGBA( redColor, greenColor, blueColor, 1 )
        else:
            annotationInfo.Color = Draft.ColorRGBA( 1.0, 1.0, 1.0, 1.0 )

        if text and len( text.strip() ) != 0:
            CompositeSingleAnnotationOverImg( img, anchor, text, frame, annotationInfo )
            
def ChangeDefaultFramePadding( frameString ):
    global framePadding
    framePadding = frameString